# ML Challenge

Sistema de busca e ranking de produtos sobre o dataset WANDS.

- **Sistema escolhido:** hybrid search (BM25 + embeddings, combinados por RRF) recupera candidatos, e um reranker LambdaMART (LightGBM) reordena os 100 primeiros.
- **Resultado:** NDCG@10 de 0,824 no test set (95 queries, execução única), contra 0,717 do BM25 baseline.
- **Documentos:** a [nota técnica](docs/nota_tecnica/nota_tecnica.pdf) resume arquitetura, dados, protocolo, resultados, ablations, latência e error analysis. O protocolo de avaliação e a tabela de resultados por split ficam em [docs/EVALUATION.md](docs/EVALUATION.md), e o diário de desenvolvimento em [docs/DEVLOG.md](docs/DEVLOG.md).

## Como executar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # instala Python 3.13, dependências e o pacote wands_search
uv run pytest      # roda os testes (cerca de 10 s; não baixam modelos)
```

Os modelos treinados já estão em `models/` e o split em `splits/`, então a busca funciona sem treinar nada.

### Buscar produtos

A busca do sistema escolhido (hybrid search + reranker sem o cross-encoder) fica em `notebooks/05_search.ipynb`: troque `QUERY` na Etapa 1.1 e execute a célula. Também dá para usar direto em Python:

```python
from wands_search import data, search

pipeline = search.SearchPipeline.load(data.load_products())  # cerca de 40 s com os embeddings em cache
response = pipeline.search("leather accent chair", k=10)
response.results            # rank, product_id, product_name, product_class, score
response.retrieval_ms, response.ranking_ms
```

Entradas inválidas (texto vazio, só espaços ou que não é texto) levantam `retrieval.InvalidQueryError`; só caracteres especiais devolve 0 resultados; texto com mais de 500 caracteres é cortado (`response.truncated`). Sem os embeddings dos produtos em `cache/embeddings/`, a primeira carga baixa os dois arquivos (66 MB cada) do GitHub Release [`embeddings-v1`](https://github.com/lubepe/ml_challenge/releases/tag/embeddings-v1) e confere o sha256 de cada um. Se o download falhar ou o sha256 não conferir, os embeddings são gerados localmente, o que leva cerca de 40 min no CPU. As URLs e os sha256 ficam em `embeddings.RELEASE_FILES`; `cached_document_vectors(..., download=False)` desliga o download.

### Notebooks

```bash
uv run jupyter lab # abre os notebooks em notebooks/
```

Para executar os notebooks no VS Code ou em outro Jupyter, registre o kernel do ambiente uma vez:

```bash
uv run python -m ipykernel install --user --name ml-challenge --display-name "Python (ml-challenge)"
```

Depois, selecione o kernel **Python (ml-challenge)**. No VS Code, também dá para selecionar diretamente o interpretador `.venv/bin/python`. Para executar um notebook do início ao fim pela linha de comando:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 notebooks/<nome>.ipynb
```

## Reproduzir os resultados

Ordem completa, do dataset à nota técnica. Os tempos são de um Intel Core i9 (macOS, só CPU) e variam com a máquina.

| Passo | Comando ou notebook | O que gera | Tempo | Precisa de |
|---|---|---|---|---|
| 1. Split | `uv run python -m wands_search.split` | `splits/query_split.csv` (já versionado) | segundos | dataset |
| 2. EDA | `01_eda.ipynb` | análise exploratória e decisões do split | ~30 s | dataset |
| 3. Lexical search | `02_bm25.ipynb` | BM25 baseline, v2 e v3, ajuste de `k1` e `b` | ~3,5 min | dataset |
| 4. Semantic e hybrid search | `03_semantic_hybrid.ipynb` | embeddings em `cache/embeddings/`, ajuste do hybrid search | ~37 min para gerar os embeddings, ou o download do Release | — |
| 5. Reranker | `04_reranker.ipynb` | tuning, validation set, ablations e seleção do sistema | ~15 min | embeddings |
| 6. Modelos salvos | `uv run python -m wands_search.train_reranker` | `models/` (já versionado) | alguns minutos, mais o download do cross-encoder (~80 MB) | embeddings |
| 7. Busca | `05_search.ipynb` | busca de ponta a ponta com o modelo salvo | ~1 min | embeddings e `models/` |
| 8. Test set | `06_test_set.ipynb` | métricas do test set | ~5 min | embeddings e `models/` |
| 9. Error analysis | `07_error_analysis.ipynb` | error analysis do sistema escolhido no validation set | ~2 min | embeddings e `models/` |
| 10. Nota técnica | `uv run python -m wands_search.technical_note` | gráficos e PDF da nota | segundos | Google Chrome |

**O test set já foi usado.** O `06_test_set.ipynb` rodou uma única vez, em 2026-11-09, depois da escolha registrada no `docs/EVALUATION.md`. Reexecutá-lo reproduz os mesmos números, mas ele não deve servir para nenhuma decisão. A tag git `test-set-run` marca o commit dessa execução.

**De onde vem cada resultado da nota técnica:**

| Seção da nota | Notebook |
|---|---|
| 4. Resultados | `03_semantic_hybrid.ipynb` e `04_reranker.ipynb` (validation set), `06_test_set.ipynb` (test set) |
| 5. O que cada parte do ranking agrega | `04_reranker.ipynb` |
| 6. Latência e custo | `06_test_set.ipynb` (latência), `02_bm25.ipynb`, `03_semantic_hybrid.ipynb` e `05_search.ipynb` (custos) |
| 7. Error analysis | `07_error_analysis.ipynb` |

Os números da nota ficam como constantes em `wands_search.technical_note`, cada um com a sua fonte no `docs/EVALUATION.md` ou nos notebooks.

## Reprodutibilidade

**Seeds:**

| Seed | Valor | Onde | Uso |
|---|---|---|---|
| `SPLIT_SEED` | 87 | [split.py](src/wands_search/split.py#L16) | split em train, validation e test set |
| `BOOTSTRAP_SEED` | 0 | [evaluate.py](src/wands_search/evaluate.py#L19) | bootstrap confidence intervals e paired bootstrap |
| `RANKER_SEED` | 0 | [reranker.py](src/wands_search/reranker.py#L21) | LightGBM e folds do GroupKFold |
| `SAMPLE_SEED` | 42 (01) e 0 (03) | notebooks 01 e 03 | amostras exibidas nas análises |
| `INSPECTION_SEED` | 0 | notebook 04 | amostra de pares para inspeção |

**Parâmetros:** ficam como constantes no código: `systems.py` (BM25 v2 e hybrid search), `reranker.py` (grade do tuning e combinações escolhidas) e `retrieval.py` (limites da query). Cada modelo em `models/` guarda no `.json` as features, os hiperparâmetros, a seed e a versão do LightGBM.

**Versões:** fixadas no `uv.lock`. O `pyproject.toml` limita o `onnxruntime` a < 1.24 só no macOS Intel, onde as versões mais novas não instalam.

**Reexecução conferida:** os notebooks 01, 02 e 04 foram reexecutados do início ao fim, e as saídas foram comparadas célula a célula com as versionadas. Todas as métricas se repetiram exatamente; só os tempos e a latência mudaram. A única exceção é uma porcentagem descritiva do `01_eda.ipynb` (`queries_positive_pct` de `has_ratings`): uma query com correlação igual a zero passa a ter um valor positivo minúsculo, por arredondamento de ponto flutuante. Esse número não é citado no texto.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `dataset/` | Dados brutos do WANDS (somente leitura) |
| `src/wands_search/` | Código reutilizável (módulos abaixo) |
| `splits/` | `query_split.csv`: set (`train`, `validation` ou `test`) de cada `query_id`, gerado por `wands_search.split` |
| `tests/` | Testes automatizados (não baixam o embedding model) |
| `notebooks/` | Análises e experimentos, numerados na ordem de "Reproduzir os resultados" |
| `models/` | Rerankers treinados por `wands_search.train_reranker`: um arquivo do LightGBM (`.txt`) e um de metadados (`.json`) por modelo. O sistema escolhido é `hybrid_reranker_no_cross_encoder`. Carregados com `reranker.load_model` |
| `cache/` | Fora do git. O embedding model e o cross-encoder (`cache/fastembed/`) e os embeddings dos produtos (`cache/embeddings/`) |
| `docs/` | [DEVLOG](docs/DEVLOG.md), [protocolo de avaliação](docs/EVALUATION.md) e a [nota técnica](docs/nota_tecnica/nota_tecnica.pdf) (texto em `nota_tecnica.md` e `style.css`; `figures/` e o PDF gerados por `wands_search.technical_note`) |

Módulos de `src/wands_search/`:

| Módulo | Conteúdo |
|---|---|
| `data.py` | Carga, parsers de campos e deduplicação de `label.csv` |
| `profiling.py` | Diagnósticos de qualidade dos dados |
| `split.py` | Split por query em train, validation e test set |
| `metrics.py` | Métricas de avaliação por query |
| `evaluate.py` | Execução de um sistema num set, bootstrap e latência; o test set fica bloqueado |
| `text.py` | Tokenização comum a queries e produtos, e texto pesquisável de cada campo |
| `retrieval.py` | Índice BM25 (`bm25s`), validação da query e hybrid search (RRF) |
| `embeddings.py` | Semantic search com `BAAI/bge-small-en-v1.5` (`fastembed`, ONNX Runtime) e cache e download dos embeddings |
| `systems.py` | BM25 v2, semantic search e hybrid search com os parâmetros escolhidos no train set |
| `ranking.py` | Candidatos do reranker, exemplos de treino e lista final |
| `features.py` | Features dos pares (query, candidato) e cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` |
| `reranker.py` | LambdaMART (`lightgbm`), tuning por GroupKFold, latência do ranking e leitura dos modelos salvos |
| `train_reranker.py` | Treino dos modelos finais no train set |
| `search.py` | Busca de ponta a ponta com o modelo salvo e tratamento de entradas inválidas |
| `error_analysis.py` | Funções da error analysis |
| `plots.py` | Estilo dos gráficos e tabelas |
| `technical_note.py` | Gráficos e PDF da nota técnica |

Convenções de desenvolvimento em [CONTRIBUTING.md](CONTRIBUTING.md). Instruções para agentes de IA em [AGENTS.md](AGENTS.md); o `CLAUDE.md` só importa o `AGENTS.md` e o `CONTRIBUTING.md`.

## Dataset

**WANDS (Wayfair ANnotation DataSet)**, um dataset público de relevância de busca em e-commerce (móveis e decoração), obtido do repositório [github.com/wayfair/WANDS](https://github.com/wayfair/WANDS) sob a licença MIT. Os arquivos em `dataset/` são os do repositório, sem modificação.

Referência: Yan Chen, Shujian Liu, Zheng Liu, Weiyi Sun, Linas Baltrunas e Benjamin Schroeder. *WANDS: Dataset for Product Search Relevance Assessment.* Proceedings of the 44th European Conference on Information Retrieval (ECIR), 2022. [Preprint](https://easychair.org/publications/preprint/wm4R).

Os arquivos são separados por **tab**, apesar da extensão `.csv`.

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `product.csv` | 42.994 | Catálogo de produtos |
| `query.csv` | 480 | Queries de busca |
| `label.csv` | 233.448 | Julgamentos de relevância (query × produto) |

### Colunas

- **`product.csv`**: `product_id`, `product_name`, `product_class`, `category hierarchy` (renomeada para `category_hierarchy` na carga), `product_description`, `product_features` (pares `chave : valor` separados por `|`), `rating_count`, `average_rating`, `review_count`
- **`query.csv`**: `query_id`, `query`, `query_class`
- **`label.csv`**: `id`, `query_id`, `product_id`, `label`

### Relacionamento

`label.csv` liga `query_id` (de `query.csv`) a `product_id` (de `product.csv`) com um `label` de relevância:

| Label | Ocorrências |
|---|---|
| Partial | 146.633 |
| Irrelevant | 61.201 |
| Exact | 25.614 |

Essas contagens são dos dados brutos. Depois de `data.deduplicate_labels`, que remove cópias exatas e pares com labels diferentes, restam 231.859 pares: Partial 145.670, Irrelevant 60.719 e Exact 25.470.
