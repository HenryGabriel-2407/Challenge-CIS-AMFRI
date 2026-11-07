import random
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from domotica_python.settings import Settings

settings = Settings()


def gerar_codigo_verificacao(tamanho: int = 6) -> str:
    """Gera um código numérico aleatório de 6 dígitos."""
    return "".join(random.choices(string.digits, k=tamanho))


def send_verification_email(to_email: str, code: str) -> bool:
    """
    Envia e-mail HTML com código de verificação de conta.
    Usado no fluxo de cadastro (confirmação de e-mail).
    """
    subject = "Verificação de Conta - Domótica"

    plain_body = (
        f"Seu código de verificação é: {code}\n\n"
        f"O código expira em 15 minutos.\n\n"
        f"Se você não criou esta conta, ignore este e-mail."
    )

    html_body = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 400px; margin: 0 auto;">
        <h2 style="text-align: center; color: #0A192F;">Verificação de Conta</h2>
        <p>Olá!</p>
        <p>Use o código abaixo para confirmar seu e-mail:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0A192F;
                         background: #E0E0E0; padding: 12px 24px; border-radius: 8px;">
                {code}
            </span>
        </div>
        <p style="color: #666; font-size: 14px;">O código expira em 15 minutos.</p>
        <p style="color: #666; font-size: 14px;">Se você não criou esta conta, ignore este e-mail.</p>
    </body>
    </html>
    """

    return _enviar_email(to_email, subject, plain_body, html_body)


def send_reset_password_email(to_email: str, code: str) -> bool:
    """
    Envia e-mail HTML com código de redefinição de senha.
    Usado no fluxo "Esqueci a senha".
    """
    subject = "Redefinição de Senha - Domótica"

    plain_body = (
        f"Seu código de redefinição de senha é: {code}\n\n"
        f"O código expira em 15 minutos.\n\n"
        f"Se você não solicitou esta redefinição, ignore este e-mail."
    )

    html_body = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 400px; margin: 0 auto;">
        <h2 style="text-align: center; color: #0A192F;">Redefinição de Senha</h2>
        <p>Olá!</p>
        <p>Use o código abaixo para redefinir sua senha:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0A192F;
                         background: #E0E0E0; padding: 12px 24px; border-radius: 8px;">
                {code}
            </span>
        </div>
        <p style="color: #666; font-size: 14px;">O código expira em 15 minutos.</p>
        <p style="color: #666; font-size: 14px;">Se você não solicitou esta redefinição, ignore este e-mail.</p>
    </body>
    </html>
    """

    return _enviar_email(to_email, subject, plain_body, html_body)


def send_mfa_email(to_email: str, code: str) -> bool:
    """Envia e-mail com código de verificação MFA (2FA)."""
    subject = "Código de Acesso - Domótica"
    plain_body = f"Seu código de acesso é: {code}\n\nO código expira em 10 minutos."
    html_body = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 400px; margin: 0 auto;">
        <h2 style="text-align: center; color: #0A192F;">Código de Acesso</h2>
        <p>Olá!</p>
        <p>Use o código abaixo para concluir seu login:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0A192F;
                         background: #E0E0E0; padding: 12px 24px; border-radius: 8px;">
                {code}
            </span>
        </div>
        <p style="color: #666; font-size: 14px;">O código expira em 10 minutos.</p>
        <p style="color: #666; font-size: 14px;">Se você não tentou fazer login, ignore este e-mail.</p>
    </body>
    </html>
    """
    return _enviar_email(to_email, subject, plain_body, html_body)


def _enviar_email(to_email: str, subject: str, plain_body: str, html_body: str) -> bool:
    """Função auxiliar que envia e-mail via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_FROM_EMAIL, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False