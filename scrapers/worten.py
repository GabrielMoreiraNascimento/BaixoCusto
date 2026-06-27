import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse
import re
import time

from scrapers.chrome_utils import obter_versao_chrome, chrome_init_lock

def pesquisar_worten(nome_produto):
    print(f"[Worten] A iniciar a pesquisa por: {nome_produto}")

    produto_formatado = urllib.parse.quote(nome_produto)
    url = f"https://www.worten.pt/search?query={produto_formatado}"

    opcoes = uc.ChromeOptions()
    opcoes.add_argument("--ignore-certificate-errors")
    
    # 1. Novo modo headless
    opcoes.add_argument('--headless=new')
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--window-size=1920,1080")
    
    # 2. Argumentos de camuflagem (Anti-Fingerprint)
    opcoes.add_argument("--disable-blink-features=AutomationControlled")
    opcoes.add_argument("--disable-infobars")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-dev-shm-usage")
    
    # 3. User-Agent real e limpo
    opcoes.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

    # Altera a 'page_load_strategy' para 'normal' (sites com React/Next.js precisam que o JS carregue por completo)
    opcoes.page_load_strategy = "normal"

    navegador = None
    resultados = []

    try:
        versao_chrome = obter_versao_chrome()

        # Garante que a criação do driver uc.Chrome está protegida pelo 'with chrome_init_lock:'
        with chrome_init_lock:
            print("[Worten] A adquirir lock para inicializar o browser...")
            navegador = uc.Chrome(options=opcoes, version_main=versao_chrome)

        navegador.set_page_load_timeout(25)
        navegador.get(url)

        # 4. Movimento humano: atraso para estabilizacao
        time.sleep(6)

        # Aceitar cookies se aparecer
        try:
            botao_cookies = navegador.find_element(
                By.XPATH,
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceitar')]"
            )
            botao_cookies.click()
            time.sleep(1)
        except Exception:
            pass

        # Scroll para forcar lazy-load
        for _ in range(3):
            navegador.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)

        # Recolher cartoes
        cartoes_produto = navegador.find_elements(By.CSS_SELECTOR, '.product-card')
        print(f"[Worten] {len(cartoes_produto)} cartoes encontrados.")

        for cartao in cartoes_produto:
            try:
                # Extrair nome do atributo data-cnstrc-item-name (mais fiavel)
                nome = cartao.get_attribute("data-cnstrc-item-name")
                if not nome:
                    # Fallback para seletores internos
                    nomes_encontrados = cartao.find_elements(
                        By.XPATH, './/*[contains(@class,"name")]'
                    )
                    if not nomes_encontrados:
                        continue
                    nome = nomes_encontrados[0].get_attribute("textContent").strip()
                if not nome:
                    continue

                titulo = nome.strip()

                # --- Rejeitar acessórios óbvios (para X / compatível com X) ---
                nome_sem_esp = titulo.lower().replace(" ", "").replace("-", "")
                termo_sem_esp = nome_produto.lower().replace(" ", "").replace("-", "")
                if (
                    f"para{termo_sem_esp}" in nome_sem_esp
                    or f"compativelcom{termo_sem_esp}" in nome_sem_esp
                    or f"compatívelcom{termo_sem_esp}" in nome_sem_esp
                ):
                    continue

                # --- CORREÇÃO DE FILTROS & BYPASS DE CONSOLAS ---
                termos_consolas = ["consola", "console", "deck", "ally", "switch", "playstation", "ps5", "xbox", "nintendo"]
                e_uma_consola = any(t in nome_produto.lower() or t in titulo.lower() for t in termos_consolas)
                
                blacklist_ativa = ["capa", "cabo", "pelicula", "reparacao", "componente", "chave", "dock", "pinca", "carregador", "suporte", "adaptador", "film", "estuche", "bolsa", "protetor", "tempered", "temperado", "hidrogel", "vidro", "silicone", "camada", "livro", "guide", "headset", "skin", "folha", " pelicula", "case", "pouch", "jogo", "gamepad", "joystick", "dualshock", "dualsense", "hdmi", "cartao", "memory", "cracha", "pulseira", "figura", "poster", "camiseta", "mousepad", "teclado", "webcam", "microfone", "rede", "ethernet"]
                if not e_uma_consola:
                    blacklist_ativa.extend(["portátil", "portatil", "pc", "desktop", "computador", "laptop"])
                    
                if any(re.search(r'\b' + re.escape(termo) + r'\b', titulo.lower()) for termo in blacklist_ativa):
                    continue

                # --- VALIDACAO POR KEYWORD CONTAINMENT ---
                palavras_pesquisa = [p for p in nome_produto.lower().split() if len(p) > 2]
                if len(palavras_pesquisa) <= 2:
                    possui_palavras = all(p in titulo.lower() for p in palavras_pesquisa)
                else:
                    match_count = sum(1 for p in palavras_pesquisa if p in titulo.lower())
                    possui_palavras = match_count >= 2
                if not possui_palavras:
                    continue

                # --- Extrair imagem ---
                imagens = cartao.find_elements(By.TAG_NAME, "img")
                url_imagem = (
                    imagens[0].get_attribute("src")
                    if imagens
                    else "https://via.placeholder.com/150"
                )

                # --- Extrair link ---
                link_produto = url
                href_attr = cartao.get_attribute("href")
                if href_attr and "worten.pt/" in href_attr:
                    link_produto = href_attr
                else:
                    for a in cartao.find_elements(By.TAG_NAME, "a"):
                        href = a.get_attribute("href")
                        if href and "worten.pt/" in href and "search" not in href and "#" not in href:
                            link_produto = href
                            break

                # --- Extrair preco do atributo data-cnstrc-item-price ---
                preco_raw = cartao.get_attribute("data-cnstrc-item-price")
                if preco_raw:
                    preco = f"{preco_raw} EUR"
                else:
                    preco_bruto = ""
                    for candidato in cartao.find_elements(By.XPATH, './/*[contains(@class,"price")]'):
                        texto = candidato.get_attribute("textContent").strip()
                        if "EUR" in texto or "euro" in texto.lower():
                            preco_bruto = texto
                            break
                    if not preco_bruto:
                        continue
                    preco_limpo = preco_bruto.replace("\n", "").replace(" ", "")
                    valores = re.findall(r"\d+(?:[.,]\d+)?", preco_limpo)
                    preco = f"{valores[0]} EUR" if valores else preco_bruto

                resultados.append({
                    "loja": "Worten",
                    "nome": nome,
                    "preco": preco,
                    "link": link_produto,
                    "imagem": url_imagem,
                })

            except Exception:
                continue

    except Exception as e:
        print(f"[Worten] Erro fatal: {e}")
    finally:
        if navegador:
            navegador.quit()

    return resultados