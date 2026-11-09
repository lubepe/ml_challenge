# ML Challenge

Sistema de busca e ranking de produtos sobre o dataset WANDS.

## Como executar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # instala Python 3.13, dependências e o pacote wands_search
uv run pytest      # roda os testes
uv run python -m wands_search.split  # regenera splits/query_split.csv (seed 87)
uv run python -m wands_search.train_reranker  # treina e salva os rerankers em models/ (alguns minutos no CPU)
uv run jupyter lab # abre os notebooks em notebooks/
```

### Buscar produtos

A busca do sistema escolhido (hybrid search + reranker sem o cross-encoder) fica em `notebooks/05_search.ipynb`: troque `QUERY` na Etapa 1.1 e execute a célula. Também dá para usar direto em Python:

```python
from wands_search import data, search

pipeline = search.SearchPipeline.load(data.load_products())  # cerca de 40 s com os embeddings em cache
response = pipeline.search("leather accent chair", k=10)
response.results            # rank, product_id, product_name, product_class, score
response.retrieval_ms, response.ranking_ms
```

Entradas inválidas (texto vazio, só espaços ou que não é texto) levantam `retrieval.InvalidQueryError`; só caracteres especiais devolve 0 resultados; texto com mais de 500 caracteres é cortado (`response.truncated`). Sem os embeddings dos produtos em `cache/embeddings/`, a primeira carga os gera, o que leva cerca de 40 min no CPU.

Para executar os notebooks no VS Code ou em outro Jupyter, registre o kernel do ambiente uma vez:

```bash
uv run python -m ipykernel install --user --name ml-challenge --display-name "Python (ml-challenge)"
```

Depois, selecione o kernel **Python (ml-challenge)**. No VS Code, também dá para selecionar diretamente o interpretador `.venv/bin/python`.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `dataset/` | Dados brutos do WANDS (somente leitura) |
| `src/wands_search/` | Código reutilizável (`data.py`: carga, parsers de campos e deduplicação de `label.csv`; `profiling.py`: diagnósticos de qualidade; `split.py`: divisão por query em treino, validação e teste; `metrics.py`: métricas de avaliação por query; `text.py`: tokenização comum a queries e produtos e texto pesquisável de cada campo; `retrieval.py`: índice BM25 (`bm25s`), busca, validação da query e hybrid search (RRF); `embeddings.py`: semantic search com embeddings de `BAAI/bge-small-en-v1.5` (`fastembed`, ONNX Runtime, sem `torch`) e cache dos embeddings dos produtos; `evaluate.py`: execução de um sistema numa parte do split, métricas, bootstrap e latência (o teste fica bloqueado); `systems.py`: BM25 v2, semantic search e hybrid search com os parâmetros escolhidos no treino; `ranking.py`: candidatos do reranker, exemplos de treino e lista final; `features.py`: features dos pares (query, candidato) e cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` (`fastembed`); `reranker.py`: LambdaMART (`lightgbm`), tuning por GroupKFold (`scikit-learn`), ablations, latência do ranking e leitura dos modelos salvos; `train_reranker.py`: treino dos modelos finais no train set; `search.py`: busca de ponta a ponta com o modelo salvo e tratamento de entradas inválidas; `error_analysis.py`: etapa com a maior perda por query, comparação de `query_class` com `product_class`, atributos em `product_features` e pares de produtos quase idênticos; `plots.py`: estilo dos gráficos e tabelas) |
| `splits/` | `query_split.csv`: parte (`train`, `validation` ou `test`) de cada `query_id`, gerado por `wands_search.split` |
| `tests/` | Testes automatizados (não baixam o embedding model) |
| `cache/` | Fora do git. O embedding model baixado (`cache/fastembed/`) e os embeddings dos produtos (`cache/embeddings/`), gerados na primeira execução do `03_semantic_hybrid.ipynb`: cerca de 5 min para o texto curto e 32 min para o longo, num CPU Intel i9. O cross-encoder do reranker (cerca de 80 MB) também é baixado em `cache/fastembed/` |
| `notebooks/` | Análises exploratórias (`01_eda.ipynb`, com um TL;DR das descobertas no topo, e `01_eda_revised.ipynb`, cópia revisada para legibilidade) e retrieval lexical (`02_bm25.ipynb`, e `02_bm25_revised.ipynb`, cópia revisada para legibilidade); semantic search e hybrid search (`03_semantic_hybrid.ipynb`); reranker (`04_reranker.ipynb`, cerca de 20 min do início ao fim no CPU: o cross-encoder e o tuning por GroupKFold dominam); busca com o sistema escolhido (`05_search.ipynb`); test set, rodado uma única vez com os modelos salvos (`06_test_set.ipynb`, cerca de 5 min); error analysis do sistema escolhido no validation set (`07_error_analysis.ipynb`, cerca de 2 min) |
| `models/` | Rerankers treinados por `wands_search.train_reranker`: um arquivo do LightGBM (`.txt`) e um de metadados (`.json`: retrieval, features, hiperparâmetros, versões) por modelo. O sistema escolhido é `hybrid_reranker_no_cross_encoder`. Carregados com `reranker.load_model` |
| `docs/` | [DEVLOG](docs/DEVLOG.md) e [protocolo de avaliação](docs/EVALUATION.md) |

Convenções de desenvolvimento em [CONTRIBUTING.md](CONTRIBUTING.md). Instruções para agentes de IA em [AGENTS.md](AGENTS.md); o `CLAUDE.md` só importa o `AGENTS.md` e o `CONTRIBUTING.md`.

## Dataset

Dados extraídos do **WANDS (Wayfair ANnotation DataSet)**, um dataset de relevância de busca em e-commerce (móveis e decoração). Os arquivos em `dataset/` são separados por **tab**, apesar da extensão `.csv`.

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `product.csv` | ~43 mil | Catálogo de produtos |
| `query.csv` | 480 | Consultas de busca |
| `label.csv` | ~233 mil | Julgamentos de relevância (query × produto) |

### Colunas

- **`product.csv`**: `product_id`, `product_name`, `product_class`, `category hierarchy` (renomeada para `category_hierarchy` na carga), `product_description`, `product_features` (pares `chave : valor` separados por `|`), `rating_count`, `average_rating`, `review_count`
- **`query.csv`**: `query_id`, `query`, `query_class`
- **`label.csv`**: `id`, `query_id`, `product_id`, `label`

### Relacionamento

`label.csv` liga `query_id` (de `query.csv`) a `product_id` (de `product.csv`) com um rótulo de relevância:

| Label | Ocorrências |
|---|---|
| Partial | 146.633 |
| Irrelevant | 61.201 |
| Exact | 25.614 |

Essas contagens são dos dados brutos. Depois de `data.deduplicate_labels`, que remove cópias exatas e pares com rótulos diferentes, restam 231.859 pares: Partial 145.670, Irrelevant 60.719 e Exact 25.470.
