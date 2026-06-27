import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import urllib.parse
import re
import time

from scrapers.chrome_utils import obter_versao_chrome, chrome_init_lock

def pesquisar_amazon(nome_produto):
    print(f"[Amazon] A iniciar a pesquisa por: {nome_produto}")

    produto_formatado = urllib.parse.quote(nome_produto)
    url = f"https://www.amazon.pt/s?k={produto_formatado}"

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
            print("[Amazon] A adquirir lock para inicializar o browser...")
            navegador = uc.Chrome(options=opcoes, version_main=versao_chrome)

        navegador.set_page_load_timeout(20)
        navegador.get(url)
        time.sleep(5)

        try:
            botao = navegador.find_element(By.ID, "sp-cc-accept")
            botao.click()
            time.sleep(1)
        except Exception:
            pass

        for _ in range(3):
            navegador.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)

        cartoes = navegador.find_elements(By.CSS_SELECTOR, '[data-component-type="s-search-result"]')
        print(f"[Amazon] {len(cartoes)} cartoes encontrados.")

        for cartao in cartoes:
            try:
                nome = ""
                link_produto = url

                titulos = cartao.find_elements(By.CSS_SELECTOR, 'h2 a span, h2 span')
                if titulos:
                    nome = titulos[0].get_attribute("textContent").strip()
                if not nome:
                    continue

                links = cartao.find_elements(By.CSS_SELECTOR, 'h2 a')
                if links:
                    href = links[0].get_attribute("href")
                    if href and "amazon.pt" in href:
                        link_produto = href

                titulo = nome

                blacklist_ativa = ["capa", "cabo", "pelicula", "reparacao", "componente", "chave", "dock", "pinca", "carregador", "suporte", "adaptador", "film", "estuche", "bolsa", "protetor", "tempered", "temperado", "hidrogel", "vidro", "silicone", "camada", "livro", "guide", "headset", "skin", "folha", " pelicula", "case", "pouch", "jogo", "gamepad", "joystick", "dualshock", "dualsense", "hdmi", "cartao", "memory", "cracha", "pulseira", "figura", "poster", "camiseta", "mousepad", "teclado", "webcam", "microfone", "rede", "ethernet"]

                if any(re.search(r'\b' + re.escape(termo) + r'\b', titulo.lower()) for termo in blacklist_ativa):
                    continue

                palavras_pesquisa = [p for p in nome_produto.lower().split() if len(p) > 2]
                if palavras_pesquisa:
                    if not all(p in titulo.lower() for p in palavras_pesquisa):
                        continue

                imagens = cartao.find_elements(By.CSS_SELECTOR, 'img.s-image')
                url_imagem = imagens[0].get_attribute("src") if imagens else "https://via.placeholder.com/150"

                preco = ""
                precos = cartao.find_elements(By.CSS_SELECTOR, '.a-price .a-offscreen')
                if precos:
                    preco = precos[0].get_attribute("textContent").strip()
                if not preco:
                    precos_inteiros = cartao.find_elements(By.CSS_SELECTOR, '.a-price-whole')
                    precos_fracoes = cartao.find_elements(By.CSS_SELECTOR, '.a-price-fraction')
                    if precos_inteiros:
                        inteiro = precos_inteiros[0].get_attribute("textContent").strip().rstrip(',')
                        fracao = precos_fracoes[0].get_attribute("textContent").strip() if precos_fracoes else "00"
                        preco = f"{inteiro}.{fracao} EUR"

                if not preco:
                    continue

                resultados.append({
                    "loja": "Amazon",
                    "nome": nome,
                    "preco": preco,
                    "link": link_produto,
                    "imagem": url_imagem
                })

            except Exception:
                continue

    except Exception as e:
        print(f"[Amazon] Erro fatal: {e}")
    finally:
        if navegador:
            navegador.quit()

    return resultados
