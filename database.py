import sqlite3
from datetime import datetime

DB_NAME = 'baixocusto.db'

def inicializar_db():
    """Cria o ficheiro da base de dados e as tabelas estruturadas"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo_pesquisa TEXT,
            loja TEXT,
            nome_produto TEXT,
            preco REAL,
            data TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utilizadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilizador_id INTEGER,
            termo_pesquisa TEXT,
            preco_alvo REAL,
            ativo INTEGER DEFAULT 1,
            FOREIGN KEY (utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
        )
    ''')

    # Migration: adicionar coluna ativo se nao existe
    try:
        cursor.execute('SELECT ativo FROM alertas LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE alertas ADD COLUMN ativo INTEGER DEFAULT 1')

    conn.commit()
    conn.close()


def salvar_preco_diario(termo, loja, nome, preco_num):
    """Salva apenas 1 registro por dia por produto: o menor preco encontrado.
    Se ja existe registro hoje, atualiza se o novo preco for menor."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    termo_lower = termo.lower().strip()
    hoje = datetime.now().strftime('%d/%m/%Y')

    cursor.execute('''
        SELECT id, preco FROM historico
        WHERE termo_pesquisa = ? AND data LIKE ?
        ORDER BY preco ASC LIMIT 1
    ''', (termo_lower, f'{hoje}%'))
    existente = cursor.fetchone()

    if existente:
        id_reg, preco_existente = existente
        if preco_num < preco_existente:
            cursor.execute('''
                UPDATE historico SET preco = ?, loja = ?, nome_produto = ?, data = ?
                WHERE id = ?
            ''', (preco_num, loja, nome, datetime.now().strftime('%d/%m/%Y %H:%M'), id_reg))
            print(f"  [DB] Preco atualizado: {preco_existente} -> {preco_num} para '{termo_lower}'")
        else:
            print(f"  [DB] Preco existente ({preco_existente}) ja e menor. Nada alterado.")
    else:
        data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        cursor.execute('''
            INSERT INTO historico (termo_pesquisa, loja, nome_produto, preco, data)
            VALUES (?, ?, ?, ?, ?)
        ''', (termo_lower, loja, nome, preco_num, data_atual))
        print(f"  [DB] Novo registro diario: {preco_num} para '{termo_lower}'")

    conn.commit()
    conn.close()


def obter_historico(termo, limite=30):
    """Recupera os registros de historico para o grafico de tendencia."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT loja, nome_produto, preco, data FROM historico
        WHERE termo_pesquisa = ?
        ORDER BY id DESC LIMIT ?
    ''', (termo.lower().strip(), limite))

    dados = cursor.fetchall()
    conn.close()
    return dados


def obter_menor_preco_hoje(termo):
    """Retorna o menor preco registrado hoje para um termo de pesquisa."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hoje = datetime.now().strftime('%d/%m/%Y')

    cursor.execute('''
        SELECT preco, loja, nome_produto FROM historico
        WHERE termo_pesquisa = ? AND data LIKE ?
        ORDER BY preco ASC LIMIT 1
    ''', (termo.lower().strip(), f'{hoje}%'))
    resultado = cursor.fetchone()
    conn.close()
    return resultado


def verificar_alertas():
    """Verifica todos os alertas ativos contra os precos diarios mais baixos.
    Retorna lista de alertas que atingiram o preco alvo."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT a.id, u.email, u.nome, a.termo_pesquisa, a.preco_alvo
        FROM alertas a
        INNER JOIN utilizadores u ON a.utilizador_id = u.id
        WHERE a.ativo = 1
    ''')
    alertas = cursor.fetchall()
    conn.close()

    atingidos = []
    for id_alerta, email, nome, termo, preco_alvo in alertas:
        resultado = obter_menor_preco_hoje(termo)
        if resultado:
            preco_atual, loja, nome_prod = resultado
            if preco_atual <= preco_alvo:
                atingidos.append({
                    'alerta_id': id_alerta,
                    'email': email,
                    'nome': nome,
                    'termo': termo,
                    'preco_alvo': preco_alvo,
                    'preco_atual': preco_atual,
                    'loja': loja,
                    'nome_produto': nome_prod,
                })

    return atingidos


def desativar_alerta(alerta_id):
    """Marca um alerta como inativo apos envio de notificacao."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE alertas SET ativo = 0 WHERE id = ?', (alerta_id,))
    conn.commit()
    conn.close()
    print(f"  [DB] Alerta #{alerta_id} desativado.")
