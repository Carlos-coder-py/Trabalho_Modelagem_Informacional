"""
Modelagem Informacional | Trilha C
Le o catalogo real de produtos (products.csv - o MESMO dataset usado no
trabalho de Recuperacao da Informacao), limpa e normaliza os dados, cria
o banco SQLite a partir de banco_dados.sql e carrega tudo, respeitando
as constraints de integridade (PK, FK, UNIQUE, CHECK).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "products.csv"
SQL_PATH = BASE_DIR / "banco_dados.sql"
DB_PATH = BASE_DIR / "catalogo.db"


# ---------------------------------------------------------------------
# 1) LIMPEZA E TRANSFORMACAO DOS DADOS (a parte "ETL")
# ---------------------------------------------------------------------

def extrair_categoria(nome_produto: str, descricao: str) -> str:
    """A categoria, na planilha original, vem embutida no final da
    coluna 'Product Name' (ex.: 'DRW1 - Westernwear-Women').

    Existe uma linha fora do padrao no dataset real ('Cologne
    Fragrance', sem o separador ' - '); nesse caso, usamos a propria
    descricao do produto para decidir a categoria, em vez de criar uma
    categoria "orfa" com um unico produto.
    """
    if " - " in nome_produto:
        return nome_produto.split(" - ")[-1].strip()

    texto = f"{nome_produto} {descricao}".lower()
    if "fragrance" in texto or "cologne" in texto or "perfume" in texto:
        return "Fragrance-Women"
    return nome_produto.strip()


def extrair_tamanhos(valor_bruto) -> list[str]:
    """A coluna 'Product Size' guarda uma LISTA de tamanhos numa unica
    celula (ex.: 'Size:Medium,Small,X-Large') -- a principal violacao
    de 1FN do dataset original. Aqui ela vira uma lista Python, que
    sera transformada em varias linhas na tabela produto_tamanho."""
    if pd.isna(valor_bruto):
        return []
    texto = str(valor_bruto).replace("Size:", "").strip()
    if texto == "" or texto.lower() == "nan":
        return []
    return [t.strip() for t in texto.split(",") if t.strip()]


def limpar_preco_tabela(mrp_bruto, preco_venda: float) -> float | None:
    """Converte o MRP para numero e aplica a mesma regra de negocio do
    CHECK constraint do banco: um preco de tabela so faz sentido se for
    >= ao preco de venda. ~1.250 linhas do dataset real trazem MRP =
    8.9 para produtos de centenas de rupias -- claramente um erro de
    captura na origem. Em vez de deixar esse lixo entrar no banco,
    tratamos como ausente (NULL)."""
    mrp = pd.to_numeric(mrp_bruto, errors="coerce")
    if pd.isna(mrp) or mrp < preco_venda:
        return None
    return round(float(mrp), 2)


def carregar_e_limpar_csv() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)

    df["nome_marca"] = df["BrandName"].astype(str).str.strip()
    df["categoria"] = df.apply(
        lambda row: extrair_categoria(row["Product Name"], row["Brand Desc"]), axis=1
    )
    df["descricao"] = df["Brand Desc"].astype(str).str.strip()
    df["codigo_produto"] = df["Product ID"].astype(str).str.strip()
    df["preco_venda"] = df["SellPrice"].astype(float)
    df["preco_tabela"] = df.apply(
        lambda row: limpar_preco_tabela(row["MRP"], row["preco_venda"]), axis=1
    )
    df["lista_tamanhos"] = df["Product Size"].apply(extrair_tamanhos)

    return df


# ---------------------------------------------------------------------
# 2) CRIACAO DO BANCO E CARGA
# ---------------------------------------------------------------------

def criar_schema(conn: sqlite3.Connection) -> None:
    ddl_sql = SQL_PATH.read_text(encoding="utf-8")
    conn.executescript(ddl_sql)


def obter_ou_criar_id(conn: sqlite3.Connection, tabela: str, coluna: str, cache: dict, valor: str) -> int:
    """Insere o valor na tabela de apoio (marca/categoria/tamanho) se
    ainda nao existir, e devolve o id -- evitando duplicar marcas e
    categorias que se repetem em centenas de produtos."""
    if valor in cache:
        return cache[valor]
    cur = conn.execute(f"INSERT OR IGNORE INTO {tabela} ({coluna}) VALUES (?)", (valor,))
    if cur.lastrowid and cur.rowcount:
        novo_id = cur.lastrowid
    else:
        novo_id = conn.execute(f"SELECT rowid FROM {tabela} WHERE {coluna} = ?", (valor,)).fetchone()[0]
    cache[valor] = novo_id
    return novo_id


def carregar_dados(conn: sqlite3.Connection, df: pd.DataFrame) -> dict:
    cache_marca: dict = {}
    cache_categoria: dict = {}
    cache_tamanho: dict = {}

    produtos_inseridos = 0
    produtos_rejeitados = 0
    itens_tamanho_inseridos = 0

    for _, row in df.iterrows():
        id_marca = obter_ou_criar_id(conn, "marca", "nome_marca", cache_marca, row["nome_marca"])
        id_categoria = obter_ou_criar_id(conn, "categoria", "nome_categoria", cache_categoria, row["categoria"])

        try:
            cur = conn.execute(
                """INSERT INTO produto
                       (codigo_produto, descricao, id_marca, id_categoria, preco_tabela, preco_venda)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row["codigo_produto"],
                    row["descricao"],
                    id_marca,
                    id_categoria,
                    row["preco_tabela"],
                    row["preco_venda"],
                ),
            )
            id_produto = cur.lastrowid
            produtos_inseridos += 1
        except sqlite3.IntegrityError as e:
            # Ex.: codigo_produto duplicado, ou violacao do CHECK de preco.
            produtos_rejeitados += 1
            print(f"  [aviso] produto '{row['codigo_produto']}' rejeitado pelo banco: {e}")
            continue

        for tamanho in row["lista_tamanhos"]:
            id_tamanho = obter_ou_criar_id(conn, "tamanho", "valor_tamanho", cache_tamanho, tamanho)
            conn.execute(
                "INSERT OR IGNORE INTO produto_tamanho (id_produto, id_tamanho) VALUES (?, ?)",
                (id_produto, id_tamanho),
            )
            itens_tamanho_inseridos += 1

    conn.commit()
    return {
        "marcas": len(cache_marca),
        "categorias": len(cache_categoria),
        "tamanhos": len(cache_tamanho),
        "produtos_inseridos": produtos_inseridos,
        "produtos_rejeitados": produtos_rejeitados,
        "itens_tamanho_inseridos": itens_tamanho_inseridos,
    }


# ---------------------------------------------------------------------
# 3) TESTES DE SANIDADE (demonstram que as constraints funcionam)
# ---------------------------------------------------------------------

def rodar_testes(conn: sqlite3.Connection) -> None:
    print("\n--- Testes de integridade ---")

    # Teste 1: tentar inserir um produto com preco_tabela < preco_venda
    # deve ser REJEITADO pelo CHECK constraint.
    try:
        conn.execute(
            """INSERT INTO produto (codigo_produto, descricao, id_marca, id_categoria,
                                     preco_tabela, preco_venda)
               VALUES ('TESTE_CHECK', 'produto de teste', 1, 1, 10.0, 999.0)"""
        )
        conn.commit()
        print("  [ERRO] o CHECK de preco_tabela >= preco_venda NAO foi respeitado!")
    except sqlite3.IntegrityError as e:
        print(f"  OK -> CHECK rejeitou preco_tabela menor que preco_venda: {e}")

    # Teste 2: tentar duplicar um codigo_produto que ja existe
    # deve ser REJEITADO pela constraint UNIQUE.
    primeiro_codigo = conn.execute("SELECT codigo_produto FROM produto LIMIT 1").fetchone()[0]
    try:
        conn.execute(
            """INSERT INTO produto (codigo_produto, descricao, id_marca, id_categoria, preco_venda)
               VALUES (?, 'duplicado de teste', 1, 1, 100.0)""",
            (primeiro_codigo,),
        )
        conn.commit()
        print("  [ERRO] a constraint UNIQUE de codigo_produto NAO foi respeitada!")
    except sqlite3.IntegrityError as e:
        print(f"  OK -> UNIQUE rejeitou codigo_produto duplicado ({primeiro_codigo}): {e}")


def mostrar_amostra_views(conn: sqlite3.Connection) -> None:
    print("\n--- Amostra: vw_catalogo_completo (3 produtos) ---")
    for linha in conn.execute("SELECT codigo_produto, nome_marca, nome_categoria, preco_venda, percentual_desconto, tamanhos_disponiveis FROM vw_catalogo_completo LIMIT 3"):
        print(" ", linha)

    print("\n--- vw_resumo_por_categoria ---")
    for linha in conn.execute("SELECT * FROM vw_resumo_por_categoria"):
        print(" ", linha)

    print("\n--- Top 5 marcas com mais produtos (vw_resumo_por_marca) ---")
    for linha in conn.execute("SELECT * FROM vw_resumo_por_marca LIMIT 5"):
        print(" ", linha)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    print("1) Lendo e limpando products.csv...")
    df = carregar_e_limpar_csv()
    print(f"   {len(df)} linhas lidas do CSV original.")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    print("2) Criando o schema (banco_dados.sql)...")
    criar_schema(conn)

    print("3) Carregando dados no banco...")
    stats = carregar_dados(conn, df)
    print(f"   marcas distintas:    {stats['marcas']}")
    print(f"   categorias distintas:{stats['categorias']}")
    print(f"   tamanhos distintos:  {stats['tamanhos']}")
    print(f"   produtos inseridos:  {stats['produtos_inseridos']}")
    print(f"   produtos rejeitados: {stats['produtos_rejeitados']}")
    print(f"   vinculos produto-tamanho: {stats['itens_tamanho_inseridos']}")

    rodar_testes(conn)
    mostrar_amostra_views(conn)

    conn.close()
    print(f"\nBanco pronto em: {DB_PATH}")


if __name__ == "__main__":
    main()
