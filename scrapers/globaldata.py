import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import re

from scrapers.chrome_utils import obter_versao_chrome, chrome_init_lock

def pesquisar_globaldata(nome_produto):
    print(f"[Globaldata] Fantasma Digitador (Modo Invisivel/Headless)...")

    url_home = "https://www.globaldata.pt/"

    opcoes = uc.ChromeOptions()
    opcoes.add_argument('--window-size=1920,1080')

    # --- MODO INVISÍVEL ATIVADO ---
    opcoes.add_argument('--headless=new')

    # Estratégia de carregamento eager para não esperar por todos os recursos
    opcoes.page_load_strategy = 'eager'

    navegador = None
    resultados = []

    try:
        versao_chrome = obter_versao_chrome()

        # Sincronizar inicialização do driver com o lock global para evitar WinError 183
        with chrome_init_lock:
            print("[Globaldata] A adquirir lock para inicializar o browser...")
            navegador = uc.Chrome(options=opcoes, version_main=versao_chrome)

        # Timeout de carregamento de 25 segundos
        navegador.set_page_load_timeout(20)

        print("[Globaldata] A abrir a pagina inicial...")
        navegador.get(url_home)
        time.sleep(3)

        try:
            botao_cookies = navegador.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceitar')]")
            botao_cookies.click()
            time.sleep(1)
        except Exception:
            pass

        print("[Globaldata] A digitar na barra de pesquisa...")
        barra_pesquisa = navegador.find_element(By.XPATH, "//input[@type='search' or @name='q' or @name='query' or contains(@class, 'search') or contains(@placeholder, 'esquisa')]")
        barra_pesquisa.clear()

        for letra in nome_produto:
            barra_pesquisa.send_keys(letra)
            time.sleep(random.uniform(0.03, 0.08))

        time.sleep(0.5)
        barra_pesquisa.send_keys(Keys.ENTER)

        print("[Globaldata] A aguardar o carregamento da pagina de resultados...")
        try:
            WebDriverWait(navegador, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".js-product-grid .product-tile"))
            )
        except Exception:
            print("  [Globaldata] Timeout a aguardar .js-product-grid .product-tile - a tentar com o que esta carregado.")

        # Seletor CSS preciso para evitar sub-divs duplicadas ou sem preço
        cartoes_produto = navegador.find_elements(By.CSS_SELECTOR, ".js-product-grid .product-tile")
        print(f"[Globaldata] {len(cartoes_produto)} cartoes de produto na pagina.")

        for index, cartao in enumerate(cartoes_produto):
            try:
                nome = ""
                link_produto = navegador.current_url

                todos_os_links = cartao.find_elements(By.TAG_NAME, 'a')
                for a in todos_os_links:
                    href = a.get_attribute("href")
                    if href and "globaldata.pt" in href:
                        link_produto = href

                    aria_label = a.get_attribute("aria-label")
                    if aria_label:
                        nome = aria_label.strip()

                if not nome:
                    textos = cartao.find_elements(By.XPATH, './/*[contains(@class, "title") or contains(@class, "name")]')
                    if textos:
                        nome = textos[0].get_attribute("textContent").strip()

                if not nome:
                    continue

                print(f"\n[{index+1}] Analisando: {nome}")
                titulo = nome

                # --- Rejeitar acessórios óbvios (para X / compatível com X) ---
                nome_sem_esp = titulo.lower().replace(" ", "").replace("-", "")
                termo_sem_esp = nome_produto.lower().replace(" ", "").replace("-", "")
                if (
                    f"para{termo_sem_esp}" in nome_sem_esp
                    or f"compativelcom{termo_sem_esp}" in nome_sem_esp
                    or f"compatívelcom{termo_sem_esp}" in nome_sem_esp
                ):
                    print("  [Globaldata] Rejeitado: Acessorio.")
                    continue

                # --- CORREÇÃO DE FILTROS & BYPASS DE CONSOLAS ---
                termos_consolas = ["consola", "console", "deck", "ally", "switch", "playstation", "ps5", "xbox", "nintendo"]
                e_uma_consola = any(t in nome_produto.lower() or t in titulo.lower() for t in termos_consolas)
                
                blacklist_ativa = ["capa", "cabo", "pelicula", "reparacao", "componente", "chave", "dock", "pinca", "carregador", "suporte", "adaptador", "film", "estuche", "bolsa", "protetor", "tempered", "temperado", "hidrogel", "vidro", "silicone", "camada", "livro", "guide", "headset", "skin", "folha", " pelicula", "case", "pouch", "jogo", "gamepad", "joystick", "dualshock", "dualsense", "hdmi", "cartao", "memory", "cracha", "pulseira", "figura", "poster", "camiseta", "mousepad", "teclado", "webcam", "microfone", "rede", "ethernet"]
                if not e_uma_consola:
                    blacklist_ativa.extend(["portátil", "portatil", "pc", "desktop", "computador", "laptop"])
                    
                if any(re.search(r'\b' + re.escape(termo) + r'\b', titulo.lower()) for termo in blacklist_ativa):
                    print(f"  [Globaldata] Rejeitado: Lista Negra.")
                    continue

                # --- VALIDACAO POR KEYWORD CONTAINMENT ---
                palavras_pesquisa = [p for p in nome_produto.lower().split() if len(p) > 2]
                if len(palavras_pesquisa) <= 2:
                    possui_palavras = all(p in titulo.lower() for p in palavras_pesquisa)
                else:
                    match_count = sum(1 for p in palavras_pesquisa if p in titulo.lower())
                    possui_palavras = match_count >= 2
                if not possui_palavras:
                    print(f"  [Globaldata] Rejeitado: palavras obrigatorias nao encontradas no titulo. ({nome})")
                    continue

                imagens = cartao.find_elements(By.TAG_NAME, 'img')
                url_imagem = imagens[0].get_attribute("src") if imagens else "https://via.placeholder.com/150"

                preco_bruto = ""
                possiveis_precos = cartao.find_elements(By.XPATH, './/*[contains(@class, "js-unit-price") or contains(@class, "price") or contains(text(), "€")]')
                for candidato in possiveis_precos:
                    texto = candidato.get_attribute("textContent").strip()
                    if "€" in texto:
                        preco_bruto = texto
                        break

                if preco_bruto == "":
                    print("  [Globaldata] Rejeitado: preco nao encontrado.")
                    continue

                # --- LIMPEZA VISUAL DO PREÇO ---
                valores_encontrados = re.findall(r'\d+(?:[.,]\d+)?', preco_bruto)
                if valores_encontrados:
                    preco = f"€{valores_encontrados[-1]}"
                else:
                    preco = preco_bruto

                print(f"  [Globaldata] APROVADO! Preco detetado: {preco}")
                resultados.append({
                    "loja": "Globaldata",
                    "nome": nome,
                    "preco": preco,
                    "link": link_produto,
                    "imagem": url_imagem
                })

            except Exception as e:
                print(f"  [Globaldata] Erro a ler cartao: {e}")
                continue

    except Exception as e:
        print(f"[Globaldata] Erro fatal: {e}")
    finally:
        if navegador:
            navegador.quit()

    return resultados