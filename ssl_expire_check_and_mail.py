import os
import ssl
import socket
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ================== 配置区 ==================

DOMAINS_FILE = "domains.txt"
TIMEOUT = 5 #超时时间
WARNING_DAYS = 5   # 到期前 5 天标红

# SMTP（如果只想打印，不发邮件，可以把 SEND_MAIL 设为 False）
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
MAIL_TO = os.getenv("MAIL_TO").split(",")
SEND_MAIL = True
MAIL_FROM = SMTP_USER

# ============================================

UTC = datetime.timezone.utc
CST = datetime.timezone(datetime.timedelta(hours=8))

def get_ssl_expire(domain: str):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expire_str = cert["notAfter"]

                expire_time = datetime.datetime.strptime(
                    expire_str, "%b %d %H:%M:%S %Y %Z"
                ).replace(tzinfo=UTC)

                now = datetime.datetime.now(UTC)
                days_left = (expire_time - now).days

                return {
                    "domain": domain,
                    "days": days_left,
                    "expire": expire_time,
                    "error": None
                }
    except Exception as e:
        return {
            "domain": domain,
            "days": -1,
            "expire": None,
            "error": str(e)
        }


def load_domains():
    with open(DOMAINS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def send_mail(content: str):
    msg = MIMEMultipart()
    msg["From"] = MAIL_FROM
    msg["To"] = ", ".join(MAIL_TO)
    msg["Subject"] = "⚠️ HTTPS 证书到期监控报告"

    msg.attach(MIMEText(content, "plain", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(MAIL_FROM, MAIL_TO, msg.as_string())


def main():
    domains = load_domains()
    results = []

    for domain in domains:
        results.append(get_ssl_expire(domain))

    # ❗️按剩余天数排序（最近到期的排前面）
    results.sort(key=lambda x: x["days"] if x["days"] >= 0 else 99999)

    lines = []
    warning_exists = False

    for item in results:
        domain = item["domain"]

        if item["error"]:
            lines.append(f"❌ {domain}\n   错误: {item['error']}\n")
            continue

        days = item["days"]
        expire = item["expire"].astimezone(CST).strftime(
	    "%Y-%m-%d %H:%M:%S CST"
	)

        if days <= WARNING_DAYS:
            warning_exists = True
            mark = "🚨 即将到期"
        else:
            mark = "✅ 正常"

        lines.append(
            f"{mark} {domain}\n"
            f"   剩余天数: {days}\n"
            f"   到期时间: {expire}\n"
        )

    report = "HTTPS 证书到期监控结果（按到期时间排序）\n\n" + "\n".join(lines)

    print(report)

    if SEND_MAIL and warning_exists:
        try:
            send_mail(report)
            print("📧 已发送告警邮件")
        except Exception as e:
            print("❌ 邮件发送失败:", e)
    elif SEND_MAIL:
        print("ℹ️ 没有即将到期的证书，未发送邮件")


if __name__ == "__main__":
    main()

