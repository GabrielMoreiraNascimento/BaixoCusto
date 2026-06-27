import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import concurrent.futures
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

from scrapers.pcdiga import pesquisar_pcdiga
from scrapers.worten import pesquisar_worten
from scrapers.globaldata import pesquisar_globaldata
from scrapers.kuantokusta import pesquisar_kuantokusta
from scrapers.amazon import pesquisar_amazon
from database import DB_NAME, inicializar_db, salvar_preco_diario, obter_historico

from filtros import extrair_preco_numerico, remover_duplicados, aplicar_filtro_matematico, aplicar_filtro_semelhanca, agrupar_produtos

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_pap_baixocusto_segura")
inicializar_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        flash("🔒 Acesso restrito! Inicia sessão ou cria uma conta para usares o comparador.", "erro")
        return redirect(url_for('login'))

    resultados_busca, chart_datas, chart_precos, grupos = [], [], [], []
    produto_procurado, mais_barato, historico_precos = None, None, []

    if request.method == 'POST':
        produto_procurado = (request.form.get('nome_produto') or '').strip()
        if not produto_procurado:
            flash("Indique o nome do produto a pesquisar.", "erro")
            return redirect(url_for('home'))

        # FIX #5: Usar concurrent.futures.wait() com timeout global de 55s.
        # Os scrapers que terminam a tempo contribuem com os seus resultados;
        # os que excedem o tempo são registados como aviso e ignorados.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            mapa_futuros = {
                executor.submit(pesquisar_pcdiga, produto_procurado): "PCDiga",
                executor.submit(pesquisar_worten, produto_procurado): "Worten",
                executor.submit(pesquisar_globaldata, produto_procurado): "Globaldata",
                executor.submit(pesquisar_kuantokusta, produto_procurado): "Kuantokusta",
                executor.submit(pesquisar_amazon, produto_procurado): "Amazon",
            }

            done, not_done = concurrent.futures.wait(
                mapa_futuros.keys(), timeout=150
            )

            # Registar scrapers que excederam o tempo limite
            for futuro_pendente in not_done:
                nome_scraper = mapa_futuros[futuro_pendente]
                print(f"[Aviso] O scraper '{nome_scraper}' excedeu o tempo limite de 150s e foi ignorado.")
                futuro_pendente.cancel()

            # Processar apenas os resultados das tarefas concluídas com sucesso
            for futuro_concluido in done:
                nome_scraper = mapa_futuros[futuro_concluido]
                try:
                    resultados_busca.extend(futuro_concluido.result())
                except Exception as e:
                    print(f"[Erro] Falha no scraper '{nome_scraper}': {e}")

        resultados_busca = remover_duplicados(resultados_busca)
        resultados_busca = aplicar_filtro_semelhanca(resultados_busca, produto_procurado)
        resultados_busca = aplicar_filtro_matematico(resultados_busca)

        resultados_busca.sort(key=lambda x: extrair_preco_numerico(x['preco']))

        grupos = agrupar_produtos(resultados_busca)

        if resultados_busca:
            mais_barato = resultados_busca[0]
            preco_num = extrair_preco_numerico(mais_barato['preco'])

            if preco_num < 999999.0:
                salvar_preco_diario(produto_procurado, mais_barato['loja'], mais_barato['nome'], preco_num)

        historico_precos = obter_historico(produto_procurado, limite=30)
        for hist in historico_precos[::-1]:
            chart_datas.append(hist[3])
            chart_precos.append(hist[2])

    return render_template('index.html', termo_pesquisado=produto_procurado, resultados=resultados_busca,
                           grupos=grupos, historico=historico_precos,
                           chart_datas=chart_datas, chart_precos=chart_precos)

@app.route('/registo', methods=['GET', 'POST'])
def registo():
    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        email = (request.form.get('email') or '').strip()
        senha = request.form.get('senha')

        if not nome or not email or not senha:
            flash("❌ Todos os campos são obrigatórios.", "erro")
            return redirect(url_for('registo'))

        senha_encriptada = generate_password_hash(senha, method='pbkdf2:sha256')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO utilizadores (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha_encriptada))
            conn.commit()
            flash("🎉 Conta criada com sucesso! Podes fazer login.", "sucesso")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("❌ Esse e-mail já está registado na nossa plataforma.", "erro")
        finally:
            conn.close()
            
    return render_template('registo.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        senha = request.form.get('senha') or ''
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, email, senha FROM utilizadores WHERE email = ?", (email,))
        utilizador = cursor.fetchone()
        conn.close()
        
        if utilizador and check_password_hash(utilizador[3], senha):
            session['user_id'] = utilizador[0]
            session['user_nome'] = utilizador[1]
            session['user_email'] = utilizador[2]
            flash(f"👋 Bem-vindo de volta, {utilizador[1]}!", "sucesso")
            return redirect(url_for('home'))
        else:
            flash("❌ E-mail ou palavra-passe incorretos.", "erro")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("🔒 Sessão encerrada com segurança.", "sucesso")
    return redirect(url_for('login'))

@app.route('/alerta', methods=['POST'])
def criar_alerta():
    if 'user_id' not in session:
        flash("⚠️ Precisas de iniciar sessão para criar alertas.", "erro")
        return redirect(url_for('login'))

    termo = (request.form.get('termo') or '').strip()
    if not termo:
        flash("❌ Termo de pesquisa em falta.", "erro")
        return redirect(url_for('home'))

    try:
        preco_alvo = float(request.form.get('preco_alvo'))
    except (TypeError, ValueError):
        flash("❌ Preço alvo inválido.", "erro")
        return redirect(url_for('home'))

    utilizador_id = session['user_id']

    conn = sqlite3.connect(DB_NAME)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alertas (utilizador_id, termo_pesquisa, preco_alvo) VALUES (?, ?, ?)",
                       (utilizador_id, termo.lower(), preco_alvo))
        conn.commit()
    finally:
        conn.close()

    flash(f"✅ Alerta Drop-Price ativado para '{termo}' a {preco_alvo}€!", "sucesso")
    return redirect(url_for('home'))

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/json')

if __name__ == '__main__':
    app.run(debug=True)