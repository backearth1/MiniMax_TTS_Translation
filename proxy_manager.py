#!/usr/bin/env python3
"""
网络代理智能管理模块
支持自动检测、手动配置、无代理等多种模式
"""

import asyncio
import aiohttp
import requests
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class ProxyManager:
    """代理管理器"""
    
    def __init__(self):
        self.cache_file = Path("proxy_cache.json")
        self.detection_cache = {}
        self.last_detection_time = 0
        self.current_proxy_config = None
        self._cache_valid = False
        self._cache_loaded = False
        # 同步加载缓存（如果存在）
        self._load_detection_cache_sync()
        
    async def get_optimal_proxy_config(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取最优的代理配置
        
        Args:
            force_refresh: 是否强制刷新检测
            
        Returns:
            最优的代理配置，None表示直连
        """
        current_time = time.time()
        cache_ttl = Config.PROXY_CONFIG.get("detection_cache_ttl", 300)
        
        # 检查缓存是否有效（修复：直连配置None也应该被缓存）
        if not force_refresh and (current_time - self.last_detection_time) < cache_ttl and hasattr(self, '_cache_valid'):
            logger.info(f"使用缓存的代理配置: {self.current_proxy_config}")
            return self.current_proxy_config
        
        # 根据配置模式选择代理
        proxy_mode = Config.PROXY_CONFIG.get("mode", "auto")
        logger.info(f"代理检测模式: {proxy_mode}")
        
        if proxy_mode == "disabled":
            # 强制禁用代理
            self.current_proxy_config = None
            logger.info("代理模式: 已禁用")
            
        elif proxy_mode == "manual":
            # 手动配置代理
            manual_config = Config.PROXY_CONFIG.get("manual", {})
            if manual_config.get("http_proxy"):
                self.current_proxy_config = {
                    "mode": "manual",
                    "http": manual_config.get("http_proxy"),
                    "https": manual_config.get("https_proxy"),
                    "ftp": manual_config.get("ftp_proxy"),
                }
                logger.info(f"代理模式: 手动配置 - {self.current_proxy_config['https']}")
            else:
                self.current_proxy_config = None
                logger.warning("手动代理配置为空，使用直连")
                
        elif proxy_mode == "auto":
            # 自动检测最优配置
            self.current_proxy_config = await self._auto_detect_optimal_proxy()
            
        else:
            logger.warning(f"未知的代理模式: {proxy_mode}，使用直连")
            self.current_proxy_config = None
        
        # 更新缓存时间和标记
        self.last_detection_time = current_time
        self._cache_valid = True  # 标记缓存有效
        
        # 保存检测结果到文件
        await self._save_detection_cache()
        
        return self.current_proxy_config
    
    async def _auto_detect_optimal_proxy(self) -> Optional[Dict[str, Any]]:
        """
        自动检测最优代理配置
        
        Returns:
            最优配置，None表示直连
        """
        logger.info("开始自动检测网络代理配置...")
        
        # 测试配置列表：直连 + 手动代理
        test_configs = [
            {"mode": "direct", "proxies": None},
        ]
        
        # 添加手动配置的代理进行测试
        manual_config = Config.PROXY_CONFIG.get("manual", {})
        if manual_config.get("http_proxy"):
            test_configs.append({
                "mode": "manual",
                "proxies": {
                    "http": manual_config.get("http_proxy"),
                    "https": manual_config.get("https_proxy"),
                    "ftp": manual_config.get("ftp_proxy"),
                }
            })
        
        # 测试每个配置
        results = []
        for config in test_configs:
            result = await self._test_proxy_config(config)
            results.append(result)
            logger.info(f"测试 {config['mode']}: 成功率={result['success_rate']:.1%}, 平均延迟={result['avg_latency']:.2f}s")
        
        # 选择最优配置
        best_config = max(results, key=lambda x: (x['success_rate'], -x['avg_latency']))
        
        if best_config['success_rate'] > 0:
            logger.info(f"选择最优配置: {best_config['config']['mode']}")
            return best_config['config']['proxies']
        else:
            logger.warning("所有代理配置测试失败，使用直连")
            return None
    
    async def _test_proxy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        测试单个代理配置
        
        Args:
            config: 代理配置
            
        Returns:
            测试结果
        """
        test_urls = Config.PROXY_CONFIG.get("test_urls", [
            "https://api.minimaxi.com/health",
            "https://www.baidu.com",
            "https://www.google.com"
        ])
        
        timeout = Config.PROXY_CONFIG.get("connection_timeout", 5)
        proxies = config.get("proxies")
        
        successful_tests = 0
        total_latency = 0
        total_tests = len(test_urls)
        
        for url in test_urls:
            try:
                start_time = time.time()
                
                # 尝试使用aiohttp进行异步测试
                try:
                    connector = aiohttp.TCPConnector() if proxies else None
                    client_timeout = aiohttp.ClientTimeout(total=timeout)
                    
                    async with aiohttp.ClientSession(
                        connector=connector, 
                        timeout=client_timeout
                    ) as session:
                        proxy_url = proxies.get('https') if proxies else None
                        async with session.get(url, proxy=proxy_url) as response:
                            if response.status == 200:
                                successful_tests += 1
                                latency = time.time() - start_time
                                total_latency += latency
                                
                except Exception as aiohttp_error:
                    # aiohttp失败，尝试requests
                    try:
                        response = requests.get(url, proxies=proxies, timeout=timeout)
                        if response.status_code == 200:
                            successful_tests += 1
                            latency = time.time() - start_time
                            total_latency += latency
                    except Exception as requests_error:
                        logger.debug(f"测试URL {url} 失败: aiohttp={aiohttp_error}, requests={requests_error}")
                        continue
                        
            except Exception as e:
                logger.debug(f"测试URL {url} 失败: {str(e)}")
                continue
        
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        avg_latency = total_latency / successful_tests if successful_tests > 0 else float('inf')
        
        return {
            "config": config,
            "success_rate": success_rate,
            "avg_latency": avg_latency,
            "successful_tests": successful_tests,
            "total_tests": total_tests
        }
    
    async def _save_detection_cache(self):
        """保存检测缓存到文件"""
        try:
            cache_data = {
                "last_detection_time": self.last_detection_time,
                "current_proxy_config": self.current_proxy_config,
                "detection_timestamp": time.time()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"保存代理缓存失败: {str(e)}")
    
    async def _load_detection_cache(self):
        """从文件加载检测缓存"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                self.last_detection_time = cache_data.get("last_detection_time", 0)
                self.current_proxy_config = cache_data.get("current_proxy_config")
                
                # 检查缓存是否仍然有效
                current_time = time.time()
                cache_ttl = Config.PROXY_CONFIG.get("detection_cache_ttl", 600)
                if (current_time - self.last_detection_time) < cache_ttl:
                    self._cache_valid = True
                    logger.info(f"已加载有效代理缓存: {self.current_proxy_config}")
                else:
                    logger.info("代理缓存已过期，需要重新检测")
                
        except Exception as e:
            logger.warning(f"加载代理缓存失败: {str(e)}")
    
    def _load_detection_cache_sync(self):
        """同步加载检测缓存（模块初始化时使用）"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                self.last_detection_time = cache_data.get("last_detection_time", 0)
                self.current_proxy_config = cache_data.get("current_proxy_config")
                
                # 检查缓存是否仍然有效
                current_time = time.time()
                cache_ttl = Config.PROXY_CONFIG.get("detection_cache_ttl", 600)
                if (current_time - self.last_detection_time) < cache_ttl:
                    self._cache_valid = True
                    print(f"✅ 已加载有效代理缓存: {self.current_proxy_config}")
                else:
                    print("⏰ 代理缓存已过期，首次API调用时将重新检测")
                
                self._cache_loaded = True
                
        except Exception as e:
            print(f"⚠️ 加载代理缓存失败: {str(e)}")
    
    async def get_proxy_for_aiohttp(self) -> Optional[str]:
        """
        获取aiohttp使用的代理URL
        
        Returns:
            代理URL字符串，None表示不使用代理
        """
        proxy_config = await self.get_optimal_proxy_config()
        if proxy_config and proxy_config.get("https"):
            return proxy_config["https"]
        return None
    
    async def get_proxy_for_requests(self) -> Optional[Dict[str, str]]:
        """
        获取requests使用的代理配置
        
        Returns:
            代理字典，None表示不使用代理
        """
        proxy_config = await self.get_optimal_proxy_config()
        if proxy_config:
            return {
                "http": proxy_config.get("http"),
                "https": proxy_config.get("https"),
                "ftp": proxy_config.get("ftp")
            }
        return None
    
    async def force_refresh_proxy_config(self):
        """强制刷新代理配置"""
        logger.info("强制刷新代理配置...")
        await self.get_optimal_proxy_config(force_refresh=True)
    
    def get_proxy_status(self) -> Dict[str, Any]:
        """
        获取当前代理状态
        
        Returns:
            代理状态信息
        """
        return {
            "mode": Config.PROXY_CONFIG.get("mode", "auto"),
            "current_config": self.current_proxy_config,
            "last_detection": self.last_detection_time,
            "cache_age": time.time() - self.last_detection_time if self.last_detection_time > 0 else 0
        }

# 全局代理管理器实例
proxy_manager = ProxyManager()

async def get_aiohttp_proxy() -> Optional[str]:
    """获取aiohttp代理配置"""
    return await proxy_manager.get_proxy_for_aiohttp()

async def get_requests_proxy() -> Optional[Dict[str, str]]:
    """获取requests代理配置"""
    return await proxy_manager.get_proxy_for_requests()

async def refresh_proxy_config():
    """刷新代理配置"""
    await proxy_manager.force_refresh_proxy_config()

def get_proxy_status() -> Dict[str, Any]:
    """获取代理状态"""
    return proxy_manager.get_proxy_status()