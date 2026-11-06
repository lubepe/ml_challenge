# Diário de desenvolvimento

Registro cronológico de passos, decisões e resultados. Adicione uma entrada a cada etapa concluída, sem apagar as anteriores. Os protocolos de avaliação ficam em [EVALUATION.md](EVALUATION.md).

## Modelo de entrada

```
### AAAA-MM-DD: título curto
- **O que foi feito:**
- **Por quê:**
- **Parâmetros/seed/versões:**
- **Resultado:** (métricas, números, caminho dos artefatos)
- **Próximo passo:**
```

## Entradas

### 2026-11-05: Exploração inicial dos dados
- **O que foi feito:** leitura dos três arquivos de `dataset/` e documentação no [README.md](../README.md). O `wands_label.csv` foi renomeado para `label.csv`.
- **Por quê:** entender o formato e as relações entre os arquivos antes de projetar o sistema.
- **Resultado:** `product.csv` com ~43 mil produtos, `query.csv` com 480 queries e `label.csv` com ~233 mil julgamentos. Distribuição dos rótulos: Partial 146.633, Irrelevant 61.201, Exact 25.614. Arquivos em TSV.
- **Próximo passo:** análise exploratória (nulos, queries sem produtos, duplicatas) e definição do protocolo de avaliação.

### 2026-11-05: Decisão sobre o separador dos arquivos
- **O que foi feito:** decidido manter TSV, sem converter para vírgula.
- **Por quê:** `product_description` tem muitas vírgulas, e o formato original do WANDS já é TSV.
- **Resultado:** leitura com `pd.read_csv(..., sep="\t")`.

### 2026-11-05: Arquivo de handover local
- **O que foi feito:** enunciado do desafio, checklist de entrega e estado do trabalho salvos num `HANDOVER.md` local.
- **Por quê:** persistir o contexto entre sessões de desenvolvimento.

### 2026-11-05: Ambiente com uv
- **O que foi feito:** projeto criado com `uv` (`pyproject.toml`, `uv.lock`, `.python-version`). Dependências principais: pandas, numpy e matplotlib. Grupo `dev`: jupyter, ipykernel e nbconvert. `.gitignore` para `.venv/` e checkpoints.
- **Por quê:** configuração reproduzível, exigida pelo desafio.
- **Parâmetros/seed/versões:** Python 3.13.5, pandas 3.1.1, numpy 2.5.4, matplotlib 3.11.2. Versões mais recentes em 2026-11-05, conferido com `uv tree --outdated`.
- **Convenção definida:** código em inglês (incluindo docstrings e mensagens); markdown dos notebooks pode ser em português.

### 2026-11-05: EDA, Etapa 1 (carga e visão geral)
- **O que foi feito:** [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), Etapa 1: parse, tipos, nulos, unicidade das chaves e duplicatas.
- **Resultado:**
  - Parse sem perda de linhas nos três arquivos.
  - Nulos em `product.csv`: `product_description` 14%; `rating_count`, `average_rating` e `review_count` 22% cada (9.452, mesma contagem); `product_class` 6,6%; `category_hierarchy` 3,6%.
  - 860 `product_class` e 188 `query_class`.
  - `label.csv` cita 42.986 dos 42.994 produtos.
  - 1.467 pares (query, produto) repetidos: 1.453 com o mesmo rótulo em todas as linhas e 14 com rótulos conflitantes. Em linhas, 1.561 são cópias exatas (ignorando o `id`) e 14 têm rótulo divergente. Os conflitos são sempre entre rótulos vizinhos: 9 Exact contra Partial e 5 Partial contra Irrelevant. 12 dos 14 estão empatados em 1 contra 1.
- **Pendente:** regra para resolver os 14 conflitos (registrar no EVALUATION.md).
- **Próximo passo:** Etapa 2, `product.csv`.

### 2026-11-05: Organização do repositório
- **O que foi feito:**
  - Convenções movidas para [CONTRIBUTING.md](../CONTRIBUTING.md), para humanos, e [AGENTS.md](../AGENTS.md), para agentes de IA. `AGENTS.md` é o nome reconhecido por várias ferramentas de IA; o [CLAUDE.md](../CLAUDE.md) só importa `AGENTS.md` e `CONTRIBUTING.md`, para que o Claude Code os carregue.
  - `DEVLOG.md` e `EVALUATION.md` movidos para `docs/`.
  - `HANDOVER.md` passou a ser local (`.gitignore`).
  - Funções do notebook extraídas para o pacote `src/wands_search/`: `data.py` para carga e `profiling.py` para diagnósticos de qualidade. Testes em `tests/`.
- **Por quê:** separar as regras do repositório do estado local de trabalho; manter uma única fonte de verdade para as convenções; reutilizar o código de carga nas próximas etapas.
- **Convenção definida:** funções reutilizáveis ficam em `src/wands_search/`, e o notebook importa do pacote.

### 2026-11-05: Propostas para o protocolo de avaliação
- **O que foi feito:** registradas no [EVALUATION.md](EVALUATION.md) a deduplicação de `label.csv` (remover 1.561 cópias exatas e excluir 14 pares conflitantes) e o tratamento de produtos sem rótulo (irrelevante na nota principal, com a porcentagem de rotulados reportada junto).
- **Por quê:** o gabarito cobre em média cerca de 1,1% do catálogo por query, e a escolha pode mudar a comparação entre sistemas.
- **Próximo passo:** confirmar o tratamento com o primeiro BM25 e implementar a deduplicação em `wands_search.data`.

### 2026-11-05: EDA, Etapa 2 (`product.csv`)
- **O que foi feito:** análise de `rating_count`, `average_rating`, `review_count`, `product_class`, `category_hierarchy`, `product_name`, `product_description` e `product_features` em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). Parsers `split_product_classes`, `split_category_hierarchy` e `parse_product_features` adicionados a `wands_search.data`, com testes.
- **Resultado:**
  - Nulos de avaliação nos mesmos 9.452 produtos; sem data, não dá para afirmar que são novos.
  - `average_rating` de 1 a 5, em passos de 0,5, com 85% em 4,5 ou 5. Contagens muito concentradas: os 10% de produtos com mais avaliações têm 79,5% de `rating_count`.
  - 601 valores individuais de `product_class` (2.247 produtos com mais de um), 273 com menos de 10 produtos.
  - Produtos sem `product_description` têm `product_name` e `product_features`.
  - 7.961 chaves de features; 69% dos produtos têm uma chave com valores diferentes (possíveis variantes).
- **Propostas:** feature "tem avaliação" em vez de imputar zero; log nas contagens; não imputar `product_class` e `category_hierarchy` por enquanto.
- **Próximo passo:** Etapa 3, `query.csv`.

### 2026-11-05: Uso de `category_hierarchy` e `query_class`
- **O que foi decidido:** `category_hierarchy` entra como texto pesquisável desde o primeiro BM25, e a semelhança com a busca será testada como feature do ranking. Sem filtro, do usuário ou automático. `query_class` não entra como entrada direta.
- **Por quê:** o dataset não registra filtros; um filtro automático errado remove os produtos certos; uma busca real não traz `query_class`.
- **Próximo passo:** medir na ablação o que a feature agrega.

### 2026-11-05: EDA, Etapa 3 (`query.csv`)
- **O que foi feito:** análise de `query` e `query_class` em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). `query_group_key` adicionada a `wands_search.profiling`, com testes.
- **Resultado:**
  - 183 dos 188 valores de `query_class` existem em `product_class`; 418 dos 601 valores individuais de `product_class` não têm query.
  - 139 dos 188 valores de `query_class` têm menos de 3 queries, então não dá para estratificar por ela.
  - As 6 queries com `query_class` nulo parecem ter erros de digitação.
  - `query` é curta (63% com até 3 palavras) e está em minúsculas; 15 têm caracteres especiais, como `36"`, enquanto `product_name` usa `18 ''`.
  - Um único par de queries quase iguais: "leather chair" e "leather chairs".
- **Propostas:** divisão aleatória por query, sem estratificação por `query_class`; o par fica na mesma parte.
- **Próximo passo:** Etapa 4, `label.csv`.

### 2026-11-05: Divisão considerando `label`
- **O que foi feito:** medido o perfil de `label` por query, depois da deduplicação proposta (231.859 pares). A proposta de divisão passou a estratificar pela fração de Exact de cada query, em 4 grupos.
- **Resultado:** 101 queries sem Exact, 1 sem Exact e sem Partial, 57 sem Irrelevant. Produtos julgados por query: mediana de 215, média de 483, de 1 a 4.329. A média citada antes esconde essa variação.
- **Atualização:** a proposta passou a combinar a fração de Exact com o número de produtos julgados por query, em 12 grupos, depois de uma simulação de 200 sorteios (detalhes em [EVALUATION.md](EVALUATION.md)). 10% das queries concentram 47% dos pares; 8 queries têm menos de 10 produtos julgados.
- **Também registrado:** `product_id` não entra como feature do ranking; medir depois da divisão quantos produtos de validação e teste não aparecem no treino.
- **Próximo passo:** Etapa 4 da EDA, com esses números no notebook.

### 2026-11-05: EDA, Etapa 4 (`label.csv`)
- **O que foi feito:** integridade, deduplicação, perfil de `label` por query e por produto, concordância entre `product_class` e `query_class` e raciocínio da divisão em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). Adicionados `data.deduplicate_labels`, `profiling.query_label_profile` e o módulo `split.py`, com testes.
- **Parâmetros/seed/versões:** simulação com 200 seeds (0 a 199) e proporção ilustrativa de 70/15/15.
- **Resultado:**
  - Integridade ok. Depois da deduplicação, 231.859 pares: 62,8% Partial, 26,2% Irrelevant, 11,0% Exact.
  - 13.605 produtos são Exact para uma query e Irrelevant para outra.
  - `product_class` contém `query_class` em 74,0% dos pares Exact, 54,4% dos Partial e 5,1% dos Irrelevant. 6.138 pares Exact não têm essa correspondência.
- **Decisão:** estratificar a divisão por `exact_fraction` e `n_judged`. Os números da simulação no notebook substituem os da simulação anterior, feita fora dele (teste até 19,1% dos pares, em vez de 18,7%).
- **Pendente:** proporção e seed finais; manter "leather chair" e "leather chairs" na mesma parte.
- **Próximo passo:** Etapa 5.

### 2026-11-05: EDA, Etapa 5 (pooling e normalização) e gráficos
- **O que foi feito:** análise de viés de pooling e de normalização de texto em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). Cinco gráficos adicionados ao notebook, com o estilo em `plots.py`. `profiling.simple_tokens`, `strip_accents` e `token_overlap` adicionadas, com testes.
- **Parâmetros/seed/versões:** 200 produtos aleatórios por query, `SAMPLE_SEED = 42`.
- **Resultado:**
  - Produtos julgados têm 48,5% das palavras da query, contra 1,8% de produtos aleatórios: há sinal de pooling.
  - Dos 12.756 casos de produto com todas as palavras da query, 83% foram julgados.
  - Palavras em comum separam pouco os rótulos: 0,672 em Exact, 0,491 em Partial e 0,424 em Irrelevant.
  - Acentos existem no catálogo e não nas queries. 36 queries têm palavras fora do catálogo.
- **Correção:** a primeira versão de `simple_tokens` quebrava `décor` em `d` e `cor`. Corrigido antes de registrar os resultados.
- **Propostas:** mesmo processamento para query e produto, com remoção de acentos.
- **Atualização:** gráficos refeitos com seaborn 0.13.2, adicionado às dependências, com títulos, eixos e notas que se explicam sozinhos e painéis em uma coluna. Convenção registrada no CONTRIBUTING.
- **Próximo passo:** fechar o protocolo de avaliação (proporção, seed, ganhos, relevância, métricas e K).

### 2026-11-05: Convenções e ambiente adicionais
- **O que foi feito:**
  - `CONTRIBUTING.md`: checklist "Antes de cada commit", terminologia (usar sempre o nome da coluna), conclusões logo abaixo da célula que as sustenta e regras de gráficos.
  - `pytest` adicionado ao grupo `dev`. Kernel Jupyter `ml-challenge` registrado (comando no README).
- **Por quê:** manter o padrão entre sessões e colaboradores, e permitir executar os notebooks no editor.
