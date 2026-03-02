"""
测试邮件发送
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.email_service import email_service


async def test_send_email():
    test_email = 'test@example.com'
    test_code = '123456'
    
    print(f"正在向 {test_email} 发送验证码...")
    success = await email_service.send_verification_code(test_email, test_code)
    
    if success:
        print("邮件发送成功！")
    else:
        print("邮件发送失败，请检查配置。")


if __name__ == "__main__":
    asyncio.run(test_send_email())

