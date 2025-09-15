# -*- coding: utf-8 -*-
"""
迁移验证工具
确保每一步迁移都不会破坏现有功能
"""
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Any

class MigrationValidator:
    """迁移验证器"""

    def __init__(self, base_url: str = "http://localhost:5215"):
        self.base_url = base_url
        self.validation_results = []

    async def validate_health_endpoint(self) -> Dict[str, Any]:
        """验证健康检查端点"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/health") as response:
                    if response.status == 200:
                        data = await response.json()

                        # 验证响应格式
                        required_fields = ["status", "timestamp", "service"]
                        missing_fields = [field for field in required_fields if field not in data]

                        result = {
                            "endpoint": "/api/health",
                            "status": "pass" if not missing_fields else "fail",
                            "response_code": response.status,
                            "response_data": data,
                            "missing_fields": missing_fields,
                            "validated_at": datetime.now().isoformat()
                        }
                    else:
                        result = {
                            "endpoint": "/api/health",
                            "status": "fail",
                            "response_code": response.status,
                            "error": f"HTTP {response.status}",
                            "validated_at": datetime.now().isoformat()
                        }
        except Exception as e:
            result = {
                "endpoint": "/api/health",
                "status": "error",
                "error": str(e),
                "validated_at": datetime.now().isoformat()
            }

        self.validation_results.append(result)
        return result

    async def validate_api_compatibility(self) -> Dict[str, Any]:
        """验证API兼容性"""
        print("🔍 开始API兼容性验证...")

        # 测试健康检查
        health_result = await self.validate_health_endpoint()
        print(f"  健康检查: {'✅' if health_result['status'] == 'pass' else '❌'}")

        # 这里可以添加更多API验证

        summary = {
            "total_tests": len(self.validation_results),
            "passed": len([r for r in self.validation_results if r["status"] == "pass"]),
            "failed": len([r for r in self.validation_results if r["status"] == "fail"]),
            "errors": len([r for r in self.validation_results if r["status"] == "error"]),
            "validated_at": datetime.now().isoformat()
        }

        print(f"📊 验证结果: {summary['passed']}/{summary['total_tests']} 通过")
        return summary

    def save_validation_report(self, filename: str = None):
        """保存验证报告"""
        if filename is None:
            filename = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            "validation_summary": {
                "total_tests": len(self.validation_results),
                "passed": len([r for r in self.validation_results if r["status"] == "pass"]),
                "failed": len([r for r in self.validation_results if r["status"] == "fail"]),
                "errors": len([r for r in self.validation_results if r["status"] == "error"])
            },
            "detailed_results": self.validation_results,
            "generated_at": datetime.now().isoformat()
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 验证报告已保存: {filename}")

async def run_migration_validation():
    """运行迁移验证"""
    validator = MigrationValidator()
    summary = await validator.validate_api_compatibility()
    validator.save_validation_report()
    return summary

if __name__ == "__main__":
    # 运行验证
    asyncio.run(run_migration_validation())