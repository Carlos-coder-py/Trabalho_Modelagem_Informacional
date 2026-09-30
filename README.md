# T1 — Modelagem Informacional
### Trilha C — Modelagem Relacional Completa, Normalização até 3FN e SQL

**Cenário:** Normalização do catálogo real de produtos de e-commerce (moda/beleza) que também é usado como corpus no trabalho de Recuperação da Informação (T1 RI) — aqui ele deixa de ser um CSV solto e passa a ser um banco relacional íntegro.

---

## 📁 Arquivos deste trabalho

| Arquivo | O que é |
|---|---|
| `products.csv` | Dataset real usado (o mesmo do trabalho de PLN) — 4.566 produtos |
| `banco_dados.sql` | Script SQL único: DDL das tabelas (PK/FK/UNIQUE/CHECK) + views analíticas |
| `main.py` | Código Python único, comentado: lê o CSV, limpa os dados e carrega no banco |
| `der.mmd` | Diagrama Entidade-Relacionamento em Mermaid.js |
| `der.png` | O mesmo DER já renderizado como imagem (para relatório/slides) |
| `README.md` | Este arquivo |
| `relatorio_executivo.pdf` | Relatório executivo (contexto, normalização, resultados, ROI) |

## ⚙️ Pré-requisitos

- Biblioteca `pandas`

```bash
pip install pandas
```

(SQLite já vem embutido no Python — nenhum servidor de banco é necessário.)

## ▶️ Como rodar

Com os 3 arquivos (`products.csv`, `banco_dados.sql`, `etl_e_carga.py`) na mesma pasta:

```bash
python main.py
```

O script faz tudo em sequência e imprime o progresso no console:

1. **Lê e limpa** o `products.csv` — extrai marca, categoria e a lista de tamanhos de cada produto, e trata os preços de tabela (MRP) inválidos (ver Seção "Qualidade de dados" abaixo).
2. **Cria o banco** executando `banco_dados.sql` (tabelas + views).
3. **Carrega os dados**, imprimindo quantas marcas, categorias, tamanhos e produtos foram inseridos.
4. **Roda 2 testes de integridade ao vivo**:
   - tenta inserir um produto com `preco_tabela` menor que `preco_venda` → rejeitado pelo `CHECK`;
   - tenta duplicar um `codigo_produto` já existente → rejeitado pelo `UNIQUE`.
5. **Mostra uma amostra das views** (`vw_catalogo_completo`, `vw_resumo_por_categoria`, `vw_resumo_por_marca`).

Ao final, o banco fica salvo em `catalogo.db`, que pode ser explorado com qualquer cliente SQLite:

```bash
sqlite3 catalogo.db "SELECT * FROM vw_resumo_por_categoria;"
```

## 🧹 Qualidade de dados (achado real do dataset)

Ao explorar o `products.csv`, **~1.250 das 4.566 linhas (≈27%)** trazem um valor de MRP (preço de tabela) claramente quebrado: `8.9`, para produtos que custam centenas de rúpias. Isso é tratado durante a limpeza (`etl_e_carga.py`) e reforçado por uma constraint `CHECK (preco_tabela IS NULL OR preco_tabela >= preco_venda)` no banco — ou seja, o próprio schema impede que esse tipo de dado inválido volte a entrar. Mais detalhes na Seção 1 do relatório executivo.

## 🔗 Relação com o trabalho de Recuperação da Informação (RI)

O `products.csv` é o mesmo dataset usado no T1 de RI/PLN, onde ele é indexado e consultado por 5 algoritmos de busca (linear, booleano, TF-IDF, BM25, LSA). Lá, ele é tratado como **corpus de texto**; aqui, ele é tratado como **dado estruturado**. Os dois trabalhos são complementares: a qualidade do dado normalizado neste projeto (descrições, marcas e categorias corretas e sem ambiguidade) é exatamente o que sustenta a qualidade da busca no outro projeto.

## 📊 Resultado da carga (dataset real)

| Tabela | Registros |
|---|---|
| marca | 57 |
| categoria | 7 |
| tamanho | 93 |
| produto | 4.566 |
| produto_tamanho (vínculos) | 13.545 |
