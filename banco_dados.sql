-- =====================================================================
-- T1 - Modelagem Informacional | Trilha C
-- Banco de Dados do Catálogo de Produtos (e-commerce moda/beleza)
--
-- Este é o MESMO catálogo de produtos usado no trabalho de Recuperação
-- da Informação (T1 RI), onde ele serve de corpus para os algoritmos de
-- busca (TF-IDF, BM25, LSA, etc). Aqui, o mesmo catálogo é modelado e
-- normalizado como um banco de dados relacional íntegro.
--
-- SGBD: SQLite (simples, sem servidor, ideal para fins de aprendizado
-- e para rodar localmente antes de subir para GitHub).
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS produto_tamanho;
DROP TABLE IF EXISTS produto;
DROP TABLE IF EXISTS tamanho;
DROP TABLE IF EXISTS categoria;
DROP TABLE IF EXISTS marca;

-- ---------------------------------------------------------------------
-- MARCA
-- Na planilha original (products.csv), o nome da marca (BrandName) se
-- repetia em toda linha de produto daquela marca. Extraída aqui como
-- entidade própria para eliminar essa redundância (regra da 3FN).
-- ---------------------------------------------------------------------
CREATE TABLE marca (
    id_marca      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_marca    TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
-- CATEGORIA
-- Na planilha original, a categoria vinha embutida dentro da coluna
-- "Product Name" (ex.: "DRW1 - Westernwear-Women"). Extraída aqui como
-- entidade própria, pelo mesmo motivo da tabela marca.
-- ---------------------------------------------------------------------
CREATE TABLE categoria (
    id_categoria    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_categoria  TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
-- TAMANHO
-- Lista de todos os tamanhos possíveis que aparecem no catálogo
-- (ex.: Small, Medium, 34-B, 3-4Y). Extraída para resolver a violação
-- de 1FN descrita abaixo, na tabela produto_tamanho.
-- ---------------------------------------------------------------------
CREATE TABLE tamanho (
    id_tamanho     INTEGER PRIMARY KEY AUTOINCREMENT,
    valor_tamanho  TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
-- PRODUTO
-- Cada linha é um produto único do catálogo (equivalente a 1 linha da
-- planilha original, já sem os dados de marca/categoria repetidos).
--
-- Regra de integridade importante: preco_tabela (MRP) só é aceito se
-- for maior ou igual ao preco_venda (SellPrice) -- caso contrário fica
-- NULL. Isso existe porque a planilha original tem ~1.250 linhas
-- (~27% do catálogo!) com MRP quebrado (valor "8.9" para produtos de
-- centenas de rúpias). O CHECK abaixo é o que barra esse tipo de erro
-- de entrar no banco.
-- ---------------------------------------------------------------------
CREATE TABLE produto (
    id_produto      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_produto  TEXT NOT NULL UNIQUE,     -- "Product ID" original (ex.: DRW1)
    descricao       TEXT NOT NULL,            -- "Brand Desc" original (texto do produto)
    id_marca        INTEGER NOT NULL REFERENCES marca(id_marca),
    id_categoria    INTEGER NOT NULL REFERENCES categoria(id_categoria),
    preco_tabela    NUMERIC(10,2),            -- MRP; NULL quando ausente/inválido na origem
    preco_venda     NUMERIC(10,2) NOT NULL,   -- SellPrice
    CHECK (preco_venda > 0),
    CHECK (preco_tabela IS NULL OR preco_tabela >= preco_venda)
);

-- ---------------------------------------------------------------------
-- PRODUTO_TAMANHO
-- Correção da principal violação de 1FN da planilha original: a coluna
-- "Product Size" guardava uma lista de tamanhos numa única célula
-- (ex.: "Size:Medium,Small,X-Large"). Aqui, cada combinação
-- produto+tamanho vira uma linha própria (relacionamento N:N).
-- ---------------------------------------------------------------------
CREATE TABLE produto_tamanho (
    id_produto  INTEGER NOT NULL REFERENCES produto(id_produto) ON DELETE CASCADE,
    id_tamanho  INTEGER NOT NULL REFERENCES tamanho(id_tamanho) ON DELETE RESTRICT,
    PRIMARY KEY (id_produto, id_tamanho)
);

CREATE INDEX idx_produto_marca     ON produto(id_marca);
CREATE INDEX idx_produto_categoria ON produto(id_categoria);


-- =====================================================================
-- VIEWS ANALÍTICAS
-- Reconstroem, sob demanda, a visão "achatada" que a planilha original
-- tentava entregar -- inclusive o campo "Discount", que na origem era
-- um texto solto ("20% off") e aqui é CALCULADO a partir de
-- preco_tabela e preco_venda (nunca armazenado), evitando que o
-- percentual fique desatualizado se um dos dois preços mudar.
-- =====================================================================

CREATE VIEW vw_catalogo_completo AS
SELECT
    p.id_produto,
    p.codigo_produto,
    p.descricao,
    m.nome_marca,
    c.nome_categoria,
    p.preco_tabela,
    p.preco_venda,
    CASE
        WHEN p.preco_tabela IS NULL OR p.preco_tabela = 0 THEN NULL
        ELSE ROUND((p.preco_tabela - p.preco_venda) * 100.0 / p.preco_tabela, 0)
    END AS percentual_desconto,
    (
        SELECT GROUP_CONCAT(t.valor_tamanho, ', ')
        FROM produto_tamanho pt
        JOIN tamanho t ON t.id_tamanho = pt.id_tamanho
        WHERE pt.id_produto = p.id_produto
    ) AS tamanhos_disponiveis
FROM produto p
JOIN marca m     ON m.id_marca = p.id_marca
JOIN categoria c ON c.id_categoria = p.id_categoria;

CREATE VIEW vw_resumo_por_categoria AS
SELECT
    c.nome_categoria,
    COUNT(*)                                   AS qtd_produtos,
    ROUND(AVG(p.preco_venda), 2)               AS preco_venda_medio,
    ROUND(AVG(
        CASE WHEN p.preco_tabela IS NOT NULL
             THEN (p.preco_tabela - p.preco_venda) * 100.0 / p.preco_tabela
        END
    ), 1)                                      AS desconto_medio_pct
FROM produto p
JOIN categoria c ON c.id_categoria = p.id_categoria
GROUP BY c.nome_categoria
ORDER BY qtd_produtos DESC;

CREATE VIEW vw_resumo_por_marca AS
SELECT
    m.nome_marca,
    COUNT(*)                     AS qtd_produtos,
    ROUND(AVG(p.preco_venda), 2) AS preco_venda_medio
FROM produto p
JOIN marca m ON m.id_marca = p.id_marca
GROUP BY m.nome_marca
ORDER BY qtd_produtos DESC;
