import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import urllib.parse
import re
import time

from scrapers.chrome_utils import obter_versao_chrome, chrome_init_lock

def pesquisar_kuantokusta(nome_produto):
    print(f"[Kuantokusta] A iniciar a pesquisa por: {nome_produto}")

    produto_formatado = urllib.parse.quote(nome_produto)
    url = f"https://www.kuantokusta.pt/search?q={produto_formatado}"

    opcoes = uc.ChromeOptions()
    opcoes.add_argument('--headless=new')
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--window-size=1920,1080")
    opcoes.add_argument("--disable-blink-features=AutomationControlled")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-dev-shm-usage")
    opcoes.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
    opcoes.page_load_strategy = 'eager'

    navegador = None
    resultados = []

    try:
        versao_chrome = obter_versao_chrome()
        with chrome_init_lock:
            print("[Kuantokusta] A adquirir lock para inicializar o browser...")
            navegador = uc.Chrome(options=opcoes, version_main=versao_chrome)

        navegador.set_page_load_timeout(20)
        navegador.get(url)
        time.sleep(5)

        try:
            botao = navegador.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceitar')]")
            botao.click()
            time.sleep(1)
        except Exception:
            pass

        for _ in range(3):
            navegador.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)

        cartoes = navegador.find_elements(By.CSS_SELECTOR, '[data-testid="product-card"], .pk-product-card, [class*="ProductCard"]')
        if not cartoes:
            cartoes = navegador.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"]')
        print(f"[Kuantokusta] {len(cartoes)} cartoes encontrados.")

        for cartao in cartoes:
            try:
                nome = ""
                link_produto = url

                href = cartao.get_attribute("href")
                if href and "kuantokusta.pt" in href:
                    link_produto = href

                nomes = cartao.find_elements(By.XPATH, './/*[contains(@class,"title") or contains(@class,"name") or contains(@class,"Title") or contains(@class,"Name")]')
                if not nomes:
                    nomes = cartao.find_elements(By.TAG_NAME, 'h2')
                if not nomes:
                    nomes = cartao.find_elements(By.TAG_NAME, 'h3')
                if nomes:
                    nome = nomes[0].get_attribute("textContent").strip()
                if not nome:
                    continue

                titulo = nome

                blacklist_ativa = ["capa", "cabo", "pelicula", "reparacao", "componente", "chave", "dock", "pinca", "carregador", "suporte", "adaptador", "film", "estuche", "bolsa", "protetor", "tempered", "temperado", "hidrogel", "vidro", "silicone", "camada", "livro", "guide", "headset", "skin", "folha", " pelicula", "case", "pouch", "jogo", "gamepad", "joystick", "dualshock", "dualsense", "hdmi", "cartao", "memory", "cracha", "pulseira", "figura", "poster", "camiseta", "mousepad", "teclado", "webcam", "microfone", "rede", "ethernet"]

                if any(re.search(r'\b' + re.escape(termo) + r'\b', titulo.lower()) for termo in blacklist_ativa):
                    continue

                palavras_pesquisa = [p for p in nome_produto.lower().split() if len(p) > 2]
                if palavras_pesquisa:
                    if not all(p in titulo.lower() for p in palavras_pesquisa):
                        continue

                imagens = cartao.find_elements(By.TAG_NAME, 'img')
                url_imagem = imagens[0].get_attribute("src") if imagens else "https://via.placeholder.com/150"

                preco = ""
                precos = cartao.find_elements(By.XPATH, './/*[contains(@class,"price") or contains(@class,"Price")]')
                for p in precos:
                    texto = p.get_attribute("textContent").strip()
                    if "EUR" in texto or "euro" in texto.lower() or re.search(r'\d+[.,]\d+', texto):
                        preco = texto
                        break

                if not preco:
                    continue

                resultados.append({
                    "loja": "Kuantokusta",
                    "nome": nome,
                    "preco": preco,
                    "link": link_produto,
                    "imagem": url_imagem
                })

            except Exception:
                continue

    except Exception as e:
        print(f"[Kuantokusta] Erro fatal: {e}")
    finally:
        if navegador:
            navegador.quit()

    return resultados
