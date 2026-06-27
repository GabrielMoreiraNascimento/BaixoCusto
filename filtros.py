import statistics
import re
import difflib

def extrair_preco_numerico(preco_texto):
    """O Extrator Invencível: Usa Regex para encontrar o número exato"""
    try:
        limpo = preco_texto.replace("€", "").replace("EUR", "").strip()
        if "." in limpo and "," in limpo:
            limpo = limpo.replace(".", "")
        limpo = limpo.replace(",", ".")
        numeros_encontrados = re.findall(r'\d+(?:\.\d+)?', limpo)
        if numeros_encontrados:
            return float(numeros_encontrados[-1])
    except Exception:
        pass
    return 999999.0

def remover_duplicados(resultados):
    """Destrói produtos clonados (mesma loja, mesmo nome e mesmo preço)"""
    resultados_unicos = []
    vistos = set()
    for item in resultados:
        assinatura = f"{item['loja']}-{item['nome']}-{item['preco']}"
        if assinatura not in vistos:
            vistos.add(assinatura)
            resultados_unicos.append(item)
    return resultados_unicos

ACessorios_BLACKLIST = [
    "capa", "cabo", "pelicula", "reparacao", "componente", "chave", "dock",
    "pinca", "carregador", "suporte", "adaptador", "film", "estuche", "bolsa",
    "protetor", "tempered", "temperado", "hidrogel", "vidro", "silicone",
    "camada", "livro", "guide", "headset", "skin", "folha", "case", "pouch",
    "película", "reparação", "acessorio", "acessório",
    "jogo", "gamepad", "joystick", "dualshock", "dualsense",
    "hdmi", "cartao", "memory", "cracha", "pulseira", "figura", "poster",
    "camiseta", "mousepad", "teclado", "webcam", "microfone", "rede", "ethernet",
]

def aplicar_filtro_semelhanca(resultados, termo_pesquisa):
    """Filtro de relevancia: exclusao por acessorios + palavras obrigatorias."""
    resultados_aprovados = []
    termo = termo_pesquisa.lower().strip()
    palavras_termo = termo.split()

    essenciais = [p for p in palavras_termo if re.search(r'\d', p)]
    suporte = [p for p in palavras_termo if not re.search(r'\d', p)]

    for item in resultados:
        nome_produto = item['nome'].lower().strip()
        nome_limpo = nome_produto.replace("-", " ")

        # 0. Exclusao por palavras de acessorio no titulo (matching por palavra inteira)
        if any(re.search(r'\b' + re.escape(acc) + r'\b', nome_limpo) for acc in ACessorios_BLACKLIST):
            print(f"  [Filtro] Rejeitado (acessorio detectado): {item['nome'][:70]}")
            continue

        # 1. Palavras com digitos: TODAS obrigatorias no titulo
        if essenciais:
            if not all(e in nome_limpo for e in essenciais):
                print(f"  [Filtro] Rejeitado (falta numero essencial): {item['nome'][:70]}")
                continue
            if suporte:
                match_count = sum(1 for p in suporte if p in nome_limpo)
                min_necessario = max(1, len(suporte) // 2 + 1)
                if match_count < min_necessario:
                    nota = difflib.SequenceMatcher(None, termo, nome_limpo).ratio()
                    if nota < 0.35:
                        print(f"  [Filtro] Rejeitado (baixa relevancia, nota {nota:.2f}): {item['nome'][:70]}")
                        continue
        else:
            # 2. Sem numero: TODAS as palavras obrigatorias
            if suporte:
                if not all(p in nome_limpo for p in suporte):
                    print(f"  [Filtro] Rejeitado (falta palavra essencial): {item['nome'][:70]}")
                    continue

        resultados_aprovados.append(item)

    return resultados_aprovados

def aplicar_filtro_matematico(resultados):
    """O Filtro Mediana: Inteligente e imune a produtos absurdamente caros"""
    precos_numericos = [extrair_preco_numerico(i['preco']) for i in resultados if extrair_preco_numerico(i['preco']) < 999999.0]
    
    if len(precos_numericos) >= 3:
        mediana_precos = statistics.median(precos_numericos)
        limite_minimo = mediana_precos * 0.40
        limite_maximo = mediana_precos * 2.0
        
        resultados_filtrados = []
        for item in resultados:
            preco_item = extrair_preco_numerico(item['preco'])
            if preco_item >= limite_minimo and preco_item <= limite_maximo:
                resultados_filtrados.append(item)
                
        return resultados_filtrados
        
    return [item for item in resultados if extrair_preco_numerico(item['preco']) < 999999.0]


MARCAS_E_SPECS = {"nvidia", "msi", "gigabyte", "asus", "evga", "zotac", "pny", "sapphire", "xfx",
                   "geforce", "radeon", "rx", "gtx",
                   "apple", "samsung", "xiaomi", "oneplus", "pixel", "sony", "huawei",
                   "smartphone", "consola", "portatil", "tablet",
                   "12gb", "16gb", "8gb", "24gb", "20gb", "10gb",
                   "gddr6x", "gddr6", "gddr7", "ddr5", "ddr4",
                   "ventus", "gaming", "strix", "tuf", "eagle", "windforce", "gamingx"}

def agrupar_produtos(resultados):
    """Agrupa produtos identicos: palavras do mais curto devem existir no mais longo,
    ignorando diferencas de marca e specs de armazenamento."""
    if not resultados:
        return []

    grupos = []
    usados = [False] * len(resultados)

    for i, item_a in enumerate(resultados):
        if usados[i]:
            continue

        grupo = [item_a]
        usados[i] = True
        palavras_a = set(item_a['nome'].lower().replace('-', ' ').replace('/', ' ').split())

        for j, item_b in enumerate(resultados):
            if usados[j]:
                continue
            palavras_b = set(item_b['nome'].lower().replace('-', ' ').replace('/', ' ').split())

            menor = palavras_a if len(palavras_a) <= len(palavras_b) else palavras_b
            maior = palavras_b if len(palavras_a) <= len(palavras_b) else palavras_a

            # Diferencas nos dois sentidos
            diff_a = palavras_a - palavras_b
            diff_b = palavras_b - palavras_a
            # Se as diferencas sao so marcas/specs, sao o mesmo produto
            eh_compativel = (diff_a <= MARCAS_E_SPECS) and (diff_b <= MARCAS_E_SPECS)

            if eh_compativel:
                grupo.append(item_b)
                usados[j] = True

        grupo.sort(key=lambda x: extrair_preco_numerico(x['preco']))
        lojas = list(dict.fromkeys([g['loja'] for g in grupo]))
        preco_menor = extrair_preco_numerico(grupo[0]['preco'])

        lojas_links = {}
        for o in grupo:
            if o['loja'] not in lojas_links:
                lojas_links[o['loja']] = o['link']

        grupos.append({
            'nome': grupo[0]['nome'],
            'preco_desde': grupo[0]['preco'],
            'preco_num': preco_menor,
            'lojas': lojas,
            'lojas_links': lojas_links,
            'num_lojas': len(lojas),
            'imagem': grupo[0]['imagem'],
            'link_mais_barato': grupo[0]['link'],
            'ofertas': grupo,
        })

    grupos.sort(key=lambda x: x['preco_num'])
    return grupos