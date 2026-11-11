# Contribuindo

Convenções do repositório, válidas para colaboradores humanos e agentes de IA.

## Ambiente

- Gerenciado com [uv](https://docs.astral.sh/uv/): `pyproject.toml`, `uv.lock` e `.python-version` (3.13).
- Instalação: `uv sync`. Isso instala as dependências e o pacote `wands_search` em modo editável.
- Dependências de desenvolvimento (jupyter, pytest etc.) ficam no grupo `dev`.
- Para adicionar uma dependência, use `uv add <pacote>` (ou `uv add --dev <pacote>`) e commite o `uv.lock` atualizado.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `dataset/` | Dados brutos do WANDS (TSV). **Somente leitura.** |
| `src/wands_search/` | Código reutilizável (carga, avaliação, retrieval, ranking) |
| `tests/` | Testes automatizados (`uv run pytest`) |
| `notebooks/` | Análises exploratórias e experimentos, numerados (`01_eda.ipynb`, ...) |
| `models/` | Rerankers treinados (`uv run python -m wands_search.train_reranker`): arquivo do LightGBM e metadados em JSON. Regenerados pelo script, nunca editados à mão |
| `docs/` | Registro de desenvolvimento e protocolo de avaliação |

## Código

- **Idioma:** todo o código fica em inglês, incluindo nomes, comentários, docstrings e mensagens de saída (`print`, logs, erros).
- **Reuso:** funções que serão usadas em mais de um lugar ficam em `src/wands_search/`, nunca definidas só no notebook. O notebook importa do pacote.
- **Testes:** todo componente essencial (carga, métricas, split, retrieval, ranking) tem testes em `tests/`.
- **Reprodutibilidade:** seeds, parâmetros e versões ficam explícitos no código ou em configuração, nunca implícitos.

## Dados

- `dataset/` nunca é alterado. Renomeações de colunas, deduplicação e limpeza acontecem no código de carga (`wands_search.data`).
- Os arquivos são TSV apesar da extensão `.csv`.

## Notebooks

Os modelos de formato são [notebooks/01_eda.ipynb](notebooks/01_eda.ipynb) e [notebooks/02_bm25.ipynb](notebooks/02_bm25.ipynb). Um notebook novo segue a mesma estrutura e os mesmos termos.

### Estrutura

1. **Cabeçalho:** título (`# NN · Título`), objetivo, regras do notebook (por exemplo, "o test set não é usado"), a seção "Como ler este notebook" e a lista de etapas.
2. **TL;DR:** as conclusões principais, cada uma com a etapa onde estão os números.
3. **Termos usados no notebook:** tabela `Termo | Significado | Exemplo` com todos os termos técnicos. Se houver métricas, uma tabela de métricas (`Métrica | O que mede | Queries`).
4. **Setup:** todos os imports e cargas de dados ficam aqui, nunca no meio do notebook.
5. **Etapas:** `## Etapa N · Título`, subetapas `### N.M · Pergunta` e, se preciso, `#### N.M.K`.

### Cada seção

- Começa com uma célula markdown que explica a pergunta, define os termos e diz o que será medido e em quais dados.
- **É autocontida:** o leitor pode não ter lido as células anteriores. Nada de referências vagas ("acima", "como assumido antes", "a proposta", "a pergunta da Etapa 1"). Cite a etapa exata e repita o fato de que a seção precisa (por exemplo, "na Etapa 1.3, 14% de `product_description` era null").
- As conclusões ficam logo abaixo da célula de código que as sustenta, e não só no fim da etapa.

### Formato das conclusões

Sempre nesta ordem; um bloco sem conteúdo é omitido.

- **Resultados:** o que as saídas mostram, um fato por item, começando por uma frase curta em negrito, com os números. Só afirmam o que as saídas mostram.
- **O que isso implica (nossa interpretação):** leituras que não foram medidas, sempre marcadas como tal.
- **Suposições:** só o que tomamos como verdadeiro sem verificar, e o que muda se não for. Fatos, definições, descrições do método e condições de medição não são suposições.
- **Limitações:** o que a medição não captura (amostra pequena, um único exemplo, uma única máquina, sem correção para comparações múltiplas etc.).
- **Hipóteses para a error analysis (não conferidas):** quando houver.
- **Escolhas e alternativas:** tabela `Escolha | Status | Alternativas`. O status é decidida, proposta ou em aberto. Toda escolha, mesmo provisória, traz as outras opções.
- **Fontes externas:** o que vier de fora do dataset, como artigos e documentação, cita o link da fonte e fica separado do que os nossos dados mostram.

### Tabelas

- Toda tabela é exibida com `plots.table(df, title, note=...)`. O título, em inglês, diz o que é medido e em quais dados; a nota define as colunas que não se explicam sozinhas.
- Blocos de `print` que funcionam como tabela viram tabelas com título. `print` fica para uma ou duas linhas de contexto.
- Evite misturar inteiros e frações na mesma coluna (o inteiro aparece como `233.0`); separe em duas tabelas ou use `print`.
- Índices e cabeçalhos numéricos ganham rótulo (`k1 = 1.2`, `b = 0.5`).

### Execução e números

- O notebook é executado do início ao fim antes de ser entregue, e cada número citado no markdown é conferido com as saídas.
- Números que mudam a cada execução (tempos, latência) são lidos da execução salva e escritos como "na execução salva, …". Não se conclui com uma única execução que um sistema é mais rápido que outro.

### Idioma

- O markdown dos notebooks é em português; o código segue a regra de idioma acima.

## Gráficos

- Feitos com seaborn, usando o estilo de `wands_search.plots`.
- Vários painéis ficam em uma coluna e múltiplas linhas, nunca lado a lado.
- Cada gráfico se explica sozinho, porque pode ser lido fora do notebook. O título diz o que é medido e em quais dados; os eixos usam nomes explícitos; termos técnicos são definidos numa nota abaixo do gráfico.
- Todo gráfico que fala em token traz uma nota explicando como o token é calculado (`plots.TOKEN_DEFINITION`).
- O texto dos gráficos fica em inglês, como o resto do código.

## Terminologia

- Ao falar de uma coluna, use sempre o nome dela (`category_hierarchy`, `product_class`, `product_description`), em texto e em código. Nada de sinônimos ou traduções, como "hierarquia", "caminho", "path" ou "classe".
- O mesmo vale para qualquer conceito do projeto: escolha um termo e use só ele.
- **Termos técnicos ficam em inglês** e são definidos antes do primeiro uso: query, catalog, label, judged pair, token, field, single field, indexed text, key:value pair, retrieval, ranking, reranker, lexical search, semantic search, hybrid search, feature, split, train set, validation set, test set, stratification, data leakage, pooling, pooling bias, null, imputation, tuning, ablation, error analysis, typo, bootstrap confidence interval, paired bootstrap.
- **Termos com sentido fixo:**
  - "rating" são só as colunas `rating_count`, `average_rating` e `review_count`; "avaliação" é só a avaliação do sistema de busca;
  - "token" é só o resultado de `text.tokenize` (ou `profiling.simple_tokens`); uma contagem por `str.split` é em "palavras";
  - "split" é a divisão (e a coluna `split`); cada parte é um "set" (train, validation ou test set);
  - um produto retornado sem `label` para a query é "sem `label`" (`no label` no código).
- **Nomes de variáveis:** descritivos, sem reuso do mesmo nome para coisas diferentes (nada de `rows` ou `order` redefinidos), e com o mesmo nome para o mesmo objeto em todos os notebooks: `products`, `queries`, `raw_labels` (`label.csv` como está), `labels` (depois de `data.deduplicate_labels`), `labels_by_query`, `query_split` (Series de `evaluate.load_split`), `query_profile`, `SETS`, `key_value_pairs`, `<sistema>_index`, `<sistema>_per_query`. Constantes em maiúsculas (`SAMPLE_SEED`, `METRICS`).

## Documentação e registro

Os documentos `.md` do projeto ficam em português. Todo passo e todo protocolo de avaliação são registrados durante o desenvolvimento:

- [docs/DEVLOG.md](docs/DEVLOG.md): diário cronológico de passos, decisões e resultados. Uma entrada por etapa concluída, sem apagar as anteriores.
- [docs/EVALUATION.md](docs/EVALUATION.md): protocolo de avaliação versionado e tabela de resultados por split. Mudanças no protocolo viram uma nova versão em vez de editar a anterior.
- **Conjunto de teste:** rodado uma única vez, depois da seleção na validação. A data fica registrada no EVALUATION.md.

## Antes de cada commit

- **README atualizado:** se o commit muda como instalar, executar, testar ou a estrutura do repositório (novo módulo, notebook, script, dependência ou comando), o [README.md](README.md) é atualizado no mesmo commit. O README sempre deve permitir executar o projeto do zero.
- **Registro atualizado:** `docs/DEVLOG.md` e, se for o caso, `docs/EVALUATION.md` refletem o que o commit contém.
- **Testes passando:** `uv run pytest`.
- **Lockfile:** se `pyproject.toml` mudou, o `uv.lock` atualizado entra no mesmo commit.
