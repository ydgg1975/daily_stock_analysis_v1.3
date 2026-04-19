# -*- coding: utf-8 -*-
"""
发送IP封堵文件邮件脚本

使用方法：
1. 确保已安装依赖：pip install python-dotenv
2. 在项目根目录创建 .env 文件，添加以下内容：
   EMAIL_SENDER=1620512746@qq.com
   EMAIL_PASSWORD=你的QQ邮箱授权码
3. 运行脚本：python scripts/send_ip_block_email.py --file "IP封堵"

注意：QQ邮箱需要使用授权码，不是登录密码。
授权码获取方式：登录QQ邮箱 -> 设置 -> 账户 -> 开启SMTP服务 -> 生成授权码
"""

import argparse
import os
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
import smtplib
from datetime import datetime

# 添加项目根目录到路径，以便导入现有模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    print("警告：未安装 python-dotenv，将使用系统环境变量")


# SMTP 服务器配置（从现有代码中复制）
SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
}


def load_environment():
    """加载环境变量"""
    if HAS_DOTENV:
        env_file = project_root / '.env'
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
            print(f"已加载环境变量: {env_file}")
        else:
            print(f"警告: 未找到 .env 文件: {env_file}")


def get_smtp_config(sender_email):
    """根据发件人邮箱获取SMTP配置"""
    domain = sender_email.split('@')[-1].lower()
    smtp_config = SMTP_CONFIGS.get(domain)
    
    if smtp_config:
        return smtp_config
    else:
        # 未知邮箱，尝试通用配置
        return {
            "server": f"smtp.{domain}",
            "port": 465,
            "ssl": True
        }


def send_email_with_attachment(
    sender_email,
    sender_password,
    receiver_email,
    subject,
    body,
    attachment_path
):
    """
    发送带附件的邮件
    
    Args:
        sender_email: 发件人邮箱
        sender_password: 发件人密码/授权码
        receiver_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        attachment_path: 附件文件路径
    
    Returns:
        bool: 是否发送成功
    """
    server = None
    
    try:
        # 检查附件文件是否存在
        attachment_path = Path(attachment_path)
        if not attachment_path.exists():
            print(f"错误: 附件文件不存在: {attachment_path}")
            return False
        
        if not attachment_path.is_file():
            print(f"错误: 附件不是文件: {attachment_path}")
            return False
        
        # 构建邮件
        msg = MIMEMultipart()
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = formataddr((str(Header('IP封堵通知', 'utf-8')), sender_email))
        msg['To'] = receiver_email
        
        # 添加正文
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加附件
        filename = attachment_path.name
        with open(attachment_path, 'rb') as f:
            # 读取文件内容并编码
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            
            # 添加附件头信息，处理中文文件名
            try:
                # 尝试使用标准格式
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
            except UnicodeEncodeError:
                # 处理中文文件名
                part.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=('utf-8', '', filename)
                )
            
            msg.attach(part)
        
        # 获取SMTP配置
        smtp_config = get_smtp_config(sender_email)
        smtp_server = smtp_config['server']
        smtp_port = smtp_config['port']
        use_ssl = smtp_config['ssl']
        
        print(f"使用SMTP服务器: {smtp_server}:{smtp_port} (SSL: {use_ssl})")
        
        # 连接SMTP服务器
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        
        # 登录
        server.login(sender_email, sender_password)
        
        # 发送邮件
        server.send_message(msg)
        
        print(f"邮件发送成功！")
        print(f"  发件人: {sender_email}")
        print(f"  收件人: {receiver_email}")
        print(f"  附件: {attachment_path}")
        
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("错误: 认证失败，请检查邮箱和授权码是否正确")
        print("提示: QQ邮箱需要使用授权码，不是登录密码")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"错误: 无法连接SMTP服务器 - {e}")
        return False
    except Exception as e:
        print(f"错误: 发送邮件失败 - {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='发送IP封堵文件邮件脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法（使用环境变量配置邮箱）
  python scripts/send_ip_block_email.py --file "IP封堵"
  
  # 指定收件人
  python scripts/send_ip_block_email.py --file "IP封堵" --to liux67@chinatelecom.cn
  
  # 完整参数
  python scripts/send_ip_block_email.py \
      --file "IP封堵" \
      --from 1620512746@qq.com \
      --password "你的授权码" \
      --to liux67@chinatelecom.cn

环境变量配置（在 .env 文件中）:
  EMAIL_SENDER=1620512746@qq.com
  EMAIL_PASSWORD=你的QQ邮箱授权码
  EMAIL_RECEIVER=liux67@chinatelecom.cn（可选）

注意事项:
  1. QQ邮箱需要使用授权码，不是登录密码
  2. 授权码获取方式：登录QQ邮箱 -> 设置 -> 账户 -> 开启SMTP服务 -> 生成授权码
  3. 附件文件路径可以是绝对路径或相对路径
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        required=True,
        help='要发送的附件文件路径（例如："IP封堵"）'
    )
    
    parser.add_argument(
        '--from', '-s',
        dest='sender',
        default=None,
        help='发件人邮箱（默认使用 EMAIL_SENDER 环境变量）'
    )
    
    parser.add_argument(
        '--password', '-p',
        default=None,
        help='发件人邮箱密码/授权码（默认使用 EMAIL_PASSWORD 环境变量）'
    )
    
    parser.add_argument(
        '--to', '-t',
        dest='receiver',
        default=None,
        help='收件人邮箱（默认使用 EMAIL_RECEIVER 环境变量，或 liux67@chinatelecom.cn）'
    )
    
    parser.add_argument(
        '--subject',
        default=None,
        help='邮件主题（默认自动生成）'
    )
    
    parser.add_argument(
        '--body',
        default=None,
        help='邮件正文（默认自动生成）'
    )
    
    args = parser.parse_args()
    
    # 加载环境变量
    load_environment()
    
    # 获取配置
    sender_email = args.sender or os.getenv('EMAIL_SENDER')
    sender_password = args.password or os.getenv('EMAIL_PASSWORD')
    receiver_email = args.receiver or os.getenv('EMAIL_RECEIVER') or 'liux67@chinatelecom.cn'
    
    # 验证必要配置
    if not sender_email:
        print("错误: 未指定发件人邮箱")
        print("请使用 --from 参数或设置 EMAIL_SENDER 环境变量")
        sys.exit(1)
    
    if not sender_password:
        print("错误: 未指定发件人密码/授权码")
        print("请使用 --password 参数或设置 EMAIL_PASSWORD 环境变量")
        sys.exit(1)
    
    # 生成默认主题和正文
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = Path(args.file).name
    
    if args.subject:
        subject = args.subject
    else:
        subject = f"IP封堵文件 - {date_str}"
    
    if args.body:
        body = args.body
    else:
        body = f"""您好，

附件是IP封堵文件：{filename}

发送时间：{date_str}

此邮件由系统自动发送，请勿回复。
"""
    
    # 发送邮件
    success = send_email_with_attachment(
        sender_email=sender_email,
        sender_password=sender_password,
        receiver_email=receiver_email,
        subject=subject,
        body=body,
        attachment_path=args.file
    )
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
