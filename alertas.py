import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from database import (
    DB_NAME, salvar_preco_diario, verificar_alertas, desativar_alerta
)


def enviar_email(destino, nome_utilizador, termo, preco_atual, loja):
    """Envia notificacao de alerta de preco via SMTP Gmail."""
    remetente = os.environ.get("SMTP_EMAIL", "baixocusto.org@gmail.com")
    senha = os.environ.get("SMTP_PASSWORD", "")

    assunto = f"ALERTA BAIXO CUSTO: O preco de {termo} baixou!"
    corpo = f"""Ola {nome_utilizador}!

O produto '{termo}' que estavas a vigiar no Baixo Custo atingiu o preco de {preco_atual}EUR na loja {loja}.

Visita o Baixo Custo para ver a oferta completa.

Um abraco,
A Equipa Baixo Custo.
"""

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destino
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, destino, msg.as_string())
        server.quit()
        print(f"  [Email] Enviado com sucesso para {destino}")
        return True
    except Exception as e:
        print(f"  [Email] Erro ao enviar: {e}")
        return False


def verificar_e_notificar():
    """Verifica alertas ativos contra precos diarios e envia notificacoes.
    Funciona como motor pos-scraping: nao faz scraping proprio."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [Alertas] A verificar alertas ativos...")

    atingidos = verificar_alertas()

    if not atingidos:
        print("  Nenhum alerta atingiu o preco alvo hoje.")
        return

    for item in atingidos:
        print(f"  [!] Alerta #{item['alerta_id']}: '{item['termo']}' a {item['preco_atual']}EUR <= alvo {item['preco_alvo']}EUR")

        sucesso = enviar_email(
            item['email'],
            item['nome'],
            item['termo'],
            item['preco_atual'],
            item['loja']
        )

        if sucesso:
            desativar_alerta(item['alerta_id'])
            print(f"  Alerta #{item['alerta_id']} concluido e desativado.")
        else:
            print(f"  Alerta #{item['alerta_id']} mantido ativo (falha no envio).")

    print(f"  Total de notificacoes enviadas: {sum(1 for i in atingidos if True)}")


if __name__ == '__main__':
    print("[Alertas] Modo manual: verificacao unica de alertas.")
    verificar_e_notificar()
