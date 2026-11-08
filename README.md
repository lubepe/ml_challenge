# ML Challenge

Sistema de busca e ranking de produtos sobre o dataset WANDS.

## Como executar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # instala Python 3.13, dependências e o pacote wands_search
uv run pytest      # roda os testes
uv run python -m wands_search.split  # regenera splits/query_split.csv (seed 87)
uv run jupyter lab # abre os notebooks em notebooks/
```

Para executar os notebooks no VS Code ou em outro Jupyter, registre o kernel do ambiente uma vez:

```bash
uv run python -m ipykernel install --user --name ml-challenge --display-name "Python (ml-challenge)"
```

Depois, selecione o kernel **Python (ml-challenge)**. No VS Code, também dá para selecionar diretamente o interpretador `.venv/bin/python`.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `dataset/` | Dados brutos do WANDS (somente leitura) |
| `src/wands_search/` | Código reutilizável (`data.py`: carga, parsers de campos e deduplicação de `label.csv`; `profiling.py`: diagnósticos de qualidade; `split.py`: divisão por query em treino, validação e teste; `plots.py`: estilo dos gráficos) |
| `splits/` | `query_split.csv`: parte (`train`, `validation` ou `test`) de cada `query_id`, gerado por `wands_search.split` |
| `tests/` | Testes automatizados |
| `notebooks/` | Análises exploratórias (`01_eda.ipynb`, com um TL;DR das descobertas no topo) |
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
