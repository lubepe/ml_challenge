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

### 2026-11-06: Fontes do WANDS, suposições e alternativas no notebook
- **O que foi feito:** leitura do artigo do WANDS (preprint da ECIR 2022), das diretrizes de anotação, do README oficial e do post da Wayfair. Nova seção no início de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb) com o resumo e os links. Conclusões do notebook agora declaram suposições e, para cada escolha, as alternativas. Convenção registrada no [CONTRIBUTING.md](../CONTRIBUTING.md).
- **Por quê:** o notebook dizia não saber como os candidatos foram escolhidos, e o artigo documenta isso. Pedido explícito de deixar suposições e alternativas visíveis.
- **Resultado:**
  - Os candidatos vieram de cliques e carrinho, Solr, busca neural e da classe prevista para a query, com parada quando a taxa de Exact caiu a 5%.
  - A concordância de `product_class` com `query_class` (Etapa 4.5) pode estar inflada, porque a seleção usou a classe prevista.
  - Produto sem rótulo não é necessariamente irrelevante: os próprios autores admitem que a completude absoluta é impossível.
  - Os 42.994 produtos são uma amostra do catálogo real, e as 480 queries não refletem o volume de buscas.
  - O artigo usa notas Exact = 1,0, Partial = 0,5 e Irrelevant = 0,0 com nDCG@10.
- **Parâmetros/seed/versões:** só células markdown mudaram; código e saídas continuam como estavam, sem reexecução.
- **Próximo passo:** executar a revisão do notebook: corrigir `split.py` e `profiling.py`, refazer as análises afetadas e reescrever textos e gráficos. As correções do protocolo entram como nova versão do [EVALUATION.md](EVALUATION.md).

### 2026-11-06: Remoção da construção do dataset do notebook
- **O que foi feito:** removida a subseção "Como o dataset foi construído" do início de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). Ajustados os trechos que dependiam dela: a suposição de completude, as células das Etapas 4.5 e 5.1 e a lista do que as fontes não informam.
- **Por quê:** a subseção confundia, e os detalhes das rodadas de seleção não mudam nenhuma decisão de avaliação ou treinamento. As consequências úteis continuam nas conclusões do notebook.
- **Parâmetros/seed/versões:** só células markdown mudaram; código e saídas continuam como estavam, sem reexecução.
- **Próximo passo:** executar a revisão do notebook, como registrado na entrada anterior.

### 2026-11-06: Distribuição de `label` antes da Etapa 2
- **O que foi feito:** nova tabela em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), logo depois da análise de pares repetidos, com a distribuição de `label` sem as cópias exatas. A tabela da Etapa 4.2 continua igual.
- **Por quê:** mostrar o balanceamento de `label` antes das etapas seguintes.
- **Parâmetros/seed/versões:** só as células de setup, de carga e a nova foram executadas; as saídas das demais continuam como estavam. A nova célula fica sem número de execução.
- **Resultado:** 231.887 linhas: Partial 145.684 (62,8%), Irrelevant 60.724 (26,2%) e Exact 25.479 (11,0%).
- **Próximo passo:** executar a revisão do notebook.

### 2026-11-06: Cobertura e concentração das colunas de avaliação
- **O que foi feito:** na Etapa 2.1 de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), novo gráfico de barras com os produtos com e sem avaliação; o gráfico de `average_rating` passou a usar % dos produtos com avaliação; nova seção "O que isso muda para nós". Proposta de ablação registrada no [EVALUATION.md](EVALUATION.md).
- **Por quê:** deixar explícito o que a concentração de `rating_count` significa para o ranking.
- **Parâmetros/seed/versões:** só as células de setup, de carga, da tabela de avaliações e dos gráficos foram executadas; as saídas das demais continuam como estavam. As células novas ou alteradas ficam sem número de execução.
- **Resultado:**
  - 33.542 produtos (78,0%) têm avaliação, e 9.452 (22,0%) não têm.
  - Entre os produtos com avaliação, 84,7% têm `average_rating` de 4,5 ou 5, e os 10% com maior `rating_count` têm 79,5% das avaliações.
  - As implicações para o ranking são interpretação, ainda não medida contra `label`.
- **Próximo passo:** testar as colunas de avaliação na ablação do ranking.

### 2026-11-06: Risco da imputação pela moda
- **O que foi feito:** nova análise na Etapa 2.3 de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), que mede o erro de imputar `product_class` e `category_hierarchy` pela moda (o valor mais comum dos produtos do mesmo grupo). Os termos são definidos no notebook. Proposta registrada no [EVALUATION.md](EVALUATION.md).
- **Por quê:** a medição anterior dava só o erro in-sample, nos mesmos produtos usados para calcular a moda, e uma imputação errada pode contradizer o que o `product_name` diz.
- **Parâmetros/seed/versões:** dos produtos com as duas colunas, 80% formam o conjunto de treino (cálculo da moda) e 20% o conjunto held-out (medição do erro), com seeds de 0 a 4. Só as células de setup, de carga, de `modal_share` e a nova foram executadas; as saídas das demais continuam como estavam.
- **Resultado:**
  - `product_class`: erro held-out de 5,9%, cerca de 157 dos 2.672 produtos imputáveis.
  - `category_hierarchy`: erro held-out de 24,3%, cerca de 335 dos 1.380 produtos imputáveis.
  - Essas estimativas supõem a mesma taxa de erro nos produtos com nulo, o que não dá para testar.
- **Próximo passo:** manter os nulos vazios no primeiro sistema e rever na análise de erros.

### 2026-11-06: Suposição sobre produção e uso de `product_class`
- **O que foi feito:** em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), registrada na Etapa 2.3 a suposição de que os nulos também existem em produção, e na Etapa 4.5 as formas de usar `product_class` sem conhecer `query_class`. Ambas também estão no [EVALUATION.md](EVALUATION.md).
- **Por quê:** a proposta de não imputar dependia de uma suposição implícita, e a busca não recebe `query_class`.
- **Parâmetros/seed/versões:** só células markdown mudaram; código e saídas continuam como estavam, sem reexecução.
- **Resultado:** proposta de começar com `product_class` no texto pesquisável e como feature de semelhança no ranking. Nada disso foi medido ainda.
- **Próximo passo:** testar essas propostas na construção do retrieval e do ranking.

### 2026-11-06: `product_id` e SKUs
- **O que foi feito:** nova análise na Etapa 2.5 de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb): valores múltiplos por chave em `product_features`, `product_id` diferentes com o mesmo texto e presença dos valores em `product_name`. Suposição e proposta registradas no [EVALUATION.md](EVALUATION.md).
- **Por quê:** entender se chaves com vários valores representam SKUs (versões vendáveis de um produto) dentro de um único `product_id`.
- **Parâmetros/seed/versões:** comparação por texto exato, sem diferenciar maiúsculas de minúsculas. Só as células de setup, de carga, de `product_features` e as novas foram executadas; `import re` foi adicionado à célula de setup.
- **Resultado:**
  - Ao que tudo indica, um `product_id` pode incluir vários SKUs: 66,3% dos produtos com `mattresssize` têm mais de um valor, e 863 têm `queen` e `king` no mesmo `product_id`.
  - Só 46 produtos (0,1%) têm `product_id` diferentes com `product_name` e `product_description` iguais.
  - Nos produtos com vários valores em `mattresssize`, nenhum aparece em `product_name` em 98,1% dos casos. Entre os 604 com um único valor, ele aparece em 73,2%.
- **Próximo passo:** testar `product_features` no texto indexado na construção do retrieval.

### 2026-11-08: EDA, seção 4.7 (`rating_count`, `average_rating` e `review_count` por `label`)
- **O que foi feito:** nova seção 4.7 em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb): junção de `label.csv` (sem duplicatas) com as colunas de avaliação de `product.csv`, tabela por `label` e um gráfico de duas linhas (fração sem avaliação e distribuição de `rating_count`). Nenhum módulo novo. O conjunto de teste não foi usado.
- **Resultado:**
  - 19,1% dos pares Exact, 24,1% dos Partial e 20,5% dos Irrelevant têm produto sem avaliação.
  - Mediana de `rating_count`: 42 em Exact, 54 em Partial, 44 em Irrelevant. Média de `average_rating`: 4,53, 4,50 e 4,52. Os três `label` quase não se diferenciam nessas colunas.
- **Proposta:** manter as três colunas como candidatas fracas ao ranking e decidir pela ablação na validação. Não foi feita análise por query nem teste de significância.

### 2026-11-08: EDA, seção 4.8 (avaliações por `label` dentro de cada query)
- **O que foi feito:** análise dentro de cada query das colunas de avaliação contra `label`, em [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). Novas funções em `profiling.py`: `within_query_spearman` e `bootstrap_mean_ci`, com testes. Seção 4.7 atualizada para apontar para a 4.8. Sem dependência nova: a correlação de Spearman é calculada como Pearson dos postos, porque o `Series.corr(method="spearman")` do pandas exige scipy.
- **Parâmetros/seed/versões:** queries com pelo menos 20 pares com valor conhecido, 2.000 reamostragens, `BOOTSTRAP_SEED = 0`. Ordem do rótulo: Irrelevant (0) < Partial (1) < Exact (2). O conjunto de teste não foi usado.
- **Resultado:** correlação média por query de 0,012 (`rating_count` em log), 0,011 (`review_count`), 0,001 (`average_rating`) e 0,017 (`has_ratings_flag`). Intervalos de 95% contêm 0, exceto `has_ratings_flag` [0,002; 0,031]. Sinal positivo em 53,0% das queries e negativo em 47,0% para `rating_count`.
- **Proposta:** manter `rating_count`, `review_count` e `has_ratings` só para a ablação; não esperar ganho sozinhos. Pendente: separar ruído de efeito real por query e testar interações.

### 2026-11-08: Revisão das regras de split
- **O que foi feito:** revisão da seção Split do [EVALUATION.md](EVALUATION.md) a partir de uma revisão do notebook (Etapa 4.6). Nenhum código nem notebook alterado; o conjunto de teste não foi usado.
- **Parâmetros/seed/versões:** checagens feitas com `deduplicate_labels` e `profiling.query_label_profile`; simulação de um split 70/15/15 com `seed = 0` só para inspeção.
- **Resultado:**
  - `n_judged` não indica dificuldade: correlação de postos com `exact_fraction` de −0,05. A mediana é 215, o p90 é 1.233 e o máximo 4.329.
  - Só 1 query não tem Exact nem Partial (`query_id` 366, "drudge report", com um par Irrelevant). 101 queries não têm Exact. 9 queries têm 90% ou mais de Irrelevant.
  - `Exact / (Exact + Partial)` ordena as queries quase como `exact_fraction` (correlação de postos 0,975).
  - Com `seed = 0`, 93% dos pares do teste têm um `product_id` também julgado no treino (esperado, o catálogo é o mesmo).
- **Propostas registradas:** excluir antes da divisão as queries sem relevante (479 restantes); manter queries quase iguais na mesma parte; trocar `exact_fraction` por `Exact / (Exact + Partial)` na estratificação, sem simulação de seeds (a checagem é no split final); distribuir o resto do arredondamento; teste de disjunção dos `query_id`; média por query e bootstrap sobre queries na avaliação.
- **Decisão:** proporção 60/20/20, porque 15% de teste dariam cerca de 70 queries e métricas muito ruidosas.
- **Decisão:** `seed = 87`, fixada antes de qualquer resultado de modelo.
- **Pendente:** reescrever a Etapa 4.6 do notebook sem a simulação de pares, que não é o critério da avaliação (as métricas são médias por query).

### 2026-11-08: Implementação do split (60/20/20, seed 87)
- **O que foi feito:** `split.py` reescrito: `relevant_queries` (exclui a query sem Exact nem Partial), `stratification_groups` com `Exact / (Exact + Partial)` (cortes 0, 5%, 25%) e `n_judged` (3 faixas), `stratified_split` com o arredondamento acumulado entre grupos e `split_queries` (queries quase iguais como bloco). `uv run python -m wands_search.split` gera `splits/query_split.csv`. Testes novos em `tests/test_split.py` (35 passando no total). Conjunto de teste não avaliado: o arquivo só atribui `query_id` a partes.
- **Parâmetros/seed/versões:** proporção 60/20/20, `seed = 87`, 479 queries.
- **Resultado:**
  - Queries por parte: 287 / 97 / 95. Menor grupo: 25 queries.
  - Mediana de `n_judged`: 217 / 218 / 211. Mediana de `Exact / (Exact + Partial)`: 0,063 / 0,065 / 0,081. Mediana da fração de Irrelevant por query: 0,074 / 0,088 / 0,078.
  - Fração de pares por `label` (Exact / Partial / Irrelevant): treino 11,2% / 64,9% / 23,9%; validação 11,6% / 58,9% / 29,5%; teste 9,8% / 61,1% / 29,1%.
  - "leather chair" e "leather chairs" (`query_id` 151 e 26) ficaram juntas, em validação.
- **Observação:** a validação e o teste têm mais Irrelevant que o treino (29% contra 24% dos pares). Não foi estratificado por isso (decisão acima); pode ser acaso. Não alterei a seed, que não pode ser escolhida olhando resultados.
- **Notebook:** Etapa 4.6 reescrita sem a simulação de pares: mostra a exclusão, os 12 grupos, o split final (tabelas por parte e um gráfico de duas linhas), com conclusões, suposições e alternativas. `split.exact_share` adicionada (36 testes passando).
- **Decisão:** ganho graduado Exact = 2, Partial = 1, Irrelevant = 0. A motivação de `exact_share` na estratificação passa a ser a mistura de Exact e Partial entre as partes, não o "nível de base" das métricas (imprecisa: uma ordem aleatória depende de `(Exact + Partial) / n_judged`). Textos corrigidos no notebook e no `EVALUATION.md`.
- **Próximo passo:** primeiro BM25 e a métrica por query na validação.
- **Correção de números:** os valores citados na entrada "Revisão das regras de split" (correlação −0,05, 9 queries com 90% ou mais de Irrelevant, 93% de produtos compartilhados) vinham de checagens avulsas, com 480 queries e uma divisão de inspeção com seed 0. Passaram para uma célula da Etapa 4.6, sobre as 479 queries e o split final: −0,013 (com `exact_share`), 8 queries e 94,7% / 92,7%. O `EVALUATION.md` e o notebook usam os novos.

### 2026-11-08: Métricas e tabela de resultados
- **O que foi feito:** registrado em [EVALUATION.md](EVALUATION.md) que as mesmas métricas (Recall@100, NDCG@10 e MRR@10, por query, em média) são calculadas na ordem de toda etapa: BM25, Vector, Hybrid (RRF) e Hybrid + reranker, com a latência na mesma tabela. Definições das métricas e do RRF adicionadas. Tabela de resultados refeita com essas colunas. Nenhum código nem avaliação rodados.
- **Decisão:** NDCG@10 é a métrica principal da comparação, com o MRR@10 ao lado, tratado como métrica de ranking aplicada ao retrieval. O Recall@100 do reranker é o do Hybrid (traço na tabela), porque ele reordena os mesmos 100 candidatos.
- **Resultado (split completo, 479 queries):**
  - Com Exact e Partial como relevantes, a mediana é 170 relevantes por query, e 353 queries têm mais de 100, então o Recall@100 tem teto médio de 0,59 mesmo para um sistema perfeito.
  - Com só Exact, a mediana é 10 e o teto médio é 0,92, mas 100 queries (das 479; as 101 da entrada anterior incluíam a query 366, já excluída) ficam sem relevante.
- **Pendente:** escolher o limiar binário de Recall@100 e MRR@10.

### 2026-11-08: Métricas revisadas (Capped Recall@100 e judged@10)
- **O que foi feito:** a tabela de métricas do [EVALUATION.md](EVALUATION.md) foi reescrita: NDCG@10, MRR@10, Capped Recall@100 e judged@10 em todas as etapas (BM25 como baseline, Vetorial, Híbrido com RRF e Híbrido + reranker). O Recall@100 sem teto saiu, por causa do teto médio de 0,59 medido na entrada anterior. Definições de Capped Recall@100 e judged@10 adicionadas. "Retrieval" e "ranking" passam a indicar o que cada métrica avalia melhor, não onde é calculada. Nenhum código nem avaliação rodados.
- **Decisão:** a única exceção na tabela é o Capped Recall@100 do reranker, igual ao do híbrido por construção.
- **Suposição:** Exact e Partial contam como relevantes no Capped Recall@100 e no MRR@10. Pendente de confirmação, principalmente para o MRR@10.
- **Observação:** a distribuição das queries sem Exact é quase igual nas partes (20,9% no treino, 20,6% na validação e 21,1% no teste), checada fora do notebook.

### 2026-11-08: Métricas finais (NDCG@10 principal; Exact como relevante em retrieval e MRR)
- **O que foi feito:** métricas do [EVALUATION.md](EVALUATION.md) reescritas. NDCG@10 (ganhos 2, 1 e 0; produto sem `label` = 0) é a métrica principal e cobre as 479 queries. Capped Recall@100 e MRR@10, com relevante = só Exact, usam as 379 queries com Exact (treino 227, validação 77, teste 75). Capped Recall @50 e @200 reportados junto com a latência do reranker para justificar K = 100. Secundárias: Capped Recall@100 com Exact e Partial, judged@10 e NDCG@10 só com produtos julgados. Nenhum código nem avaliação rodados.
- **Resultado (medido fora do notebook):** 100 das 479 queries não têm Exact (20,9%), quase igual nas três partes. 74 das 379 têm mais de 100 Exact, então o teto só muda a conta nelas; o valor máximo sem teto teria média de 0,92 em @100 (0,81 em @50 e 0,97 em @200).
- **Correção:** a especificação citava 101 queries sem Exact e n = 378; na base de 479 são 100 e 379. O texto sobre "101 ficam sem relevante" da entrada anterior e da Etapa 4.6 do notebook foi corrigido.
- **Substitui:** a suposição anterior de Exact e Partial como relevantes em Recall@100 e MRR@10, e a proposta de produto sem `label` como irrelevante, agora decidida.
- **Pendente:** definir exatamente o "NDCG@10 só com produtos julgados" ao implementar; K de retrieval e RRF (constante) a escolher.

### 2026-11-08: Revisão do notebook e TL;DR
- **O que foi feito:** novo TL;DR no topo de [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), logo depois do título, com as principais descobertas, decisões e próximos passos em linguagem para leitores não técnicos. Cada ponto indica a etapa de onde vêm os números. Revisão dos textos do notebook e dos documentos:
  - Etapa 2.4: a suposição sobre produtos sem `product_description` contradizia a conclusão logo acima; reescrita.
  - Etapas 4.2 e 4.3: o limiar binário das métricas e as queries sem Exact aparecem como decididos, conforme o [EVALUATION.md](EVALUATION.md) (só Exact; 100 queries sem Exact entre as 479; n = 379).
  - Etapa 5.1: produto sem rótulo com ganho 0 no NDCG@10 e judged@10 aparecem como decididos, não mais como proposta.
  - Etapas 4.5 e 5.1: "prevista na revisão" trocado por "ainda não foi feita", para deixar claro que as correções estão pendentes.
  - Etapas 4.7 e 4.8: `has_ratings` e `has_ratings_flag` explicados como a mesma informação.
  - [EVALUATION.md](EVALUATION.md): a simulação de 200 seeds não está mais na Etapa 4.6; o texto agora diz isso.
  - DEVLOG: entradas reordenadas em ordem cronológica (as de 2026-11-06 estavam no topo e da mais nova para a mais antiga). Nenhuma entrada foi apagada.
- **Parâmetros/seed/versões:** só células markdown mudaram; código e saídas continuam como estavam, sem reexecução. O conjunto de teste não foi usado.
- **Pendente:** a citação da literatura para *pseudo-relevance feedback* (Etapa 4.5) continua sem link, porque a fonte não pôde ser aberta nesta sessão.
- **Próximo passo:** fechar o protocolo em [EVALUATION.md](EVALUATION.md) e construir o primeiro BM25.

### 2026-11-08: Plano do BM25 e decisões de retrieval
- **O que foi feito:** plano da etapa de retrieval lexical e três decisões, sem código nem avaliação. Commit da EDA (`c820de0`, branch `eda`) antes de começar.
- **Decisões:**
  - Biblioteca `bm25s` para o BM25. Alternativas: `rank_bm25` (Python puro, lenta para 43 mil produtos), Pyserini (exige Java), implementação própria com `scipy.sparse`.
  - Baseline do retrieval com um único campo: `product_name`, `product_class`, `category_hierarchy`, `product_description` e os valores de `product_features` emendados, com um índice BM25 sobre esse texto. Os índices por campo, um para cada coluna, são montados à parte, a partir da tabela de produtos, só quando forem usados: na etapa do reranker, como features, ou no ajuste, se testarmos o retrieval por campo (soma ponderada ou BM25F). O índice do campo único não pode dar notas por campo, porque ao emendar os textos perde a origem de cada palavra.
  - `k1`, `b` e as variantes são ajustados no treino e medidos uma única vez na validação (registrado no [EVALUATION.md](EVALUATION.md), seção "Ajuste de hiperparâmetros do retrieval").
- **Parâmetros/seed/versões:** nenhum ainda. O conjunto de teste não foi usado.
- **Próximo passo:** etapa 1 do plano, `metrics.py` com testes.

### 2026-11-08: Módulo de métricas (etapa 1 do BM25)
- **O que foi feito:** novo `src/wands_search/metrics.py` com NDCG@10, NDCG@10 na *condensed list* (só produtos julgados), MRR@10, Capped Recall@K (Exact, e Exact e Partial), judged@10, e as funções `labels_by_query`, `evaluate_run` (uma linha por query) e `summarize` (média e n por métrica). 28 testes novos em `tests/test_metrics.py`, com exemplos calculados à mão (64 testes passando no total).
- **Decisões de implementação:** registradas no [EVALUATION.md](EVALUATION.md): ganho linear no NDCG, *condensed list* removendo os não julgados antes do corte, denominador do judged@10 e NaN para métrica sem definição na query. Lista repetindo um `product_id` gera erro.
- **Resultado:** conferência com a ordem ideal: todas as métricas valem 1,0, com n = 287/227 no treino e 97/77 na validação, iguais aos do protocolo. O teste não foi usado.
- **Próximo passo:** etapa 2, processamento de texto (`text.py`).

### 2026-11-08: Comparação entre sistemas e critério de seleção
- **O que foi feito:** registrados no [EVALUATION.md](EVALUATION.md) o bootstrap pareado sobre queries e o critério de seleção. Nenhum código nem avaliação rodados.
- **Decisões:**
  - Bootstrap pareado (2.000 sorteios, `BOOTSTRAP_SEED = 0`, intervalo de 95%) em toda comparação na validação, ao longo do projeto, para cada métrica. Não se aplica ao ajuste no treino.
  - Critério de seleção, aplicado uma vez no final: o sistema de maior NDCG@10 na validação, a não ser que o intervalo da diferença para um sistema mais simples inclua 0.
  - Ablações lidas como descrição, não como testes de aprovação.
- **Pendente:** "mesmo conjunto de candidatos para todos os sistemas" continua a definir.
- **Próximo passo:** etapa 2, `text.py`.

### 2026-11-08: Uso do conjunto de teste
- **O que foi feito:** registrado no [EVALUATION.md](EVALUATION.md), seção "Seleção e teste", como o teste é usado. Nenhum código nem avaliação rodados.
- **Decisão:** no fim do projeto, o sistema escolhido é registrado antes, e depois os quatro sistemas (BM25, Vetorial, Híbrido, Híbrido + reranker) rodam no teste numa única execução. Um resultado melhor de outro sistema no teste não muda a escolha. As ablações ficam só na validação. Alternativa descartada: rodar só o sistema escolhido.
- **Próximo passo:** etapa 2, `text.py`.

### 2026-11-08: Processamento de texto (etapa 2 do BM25)
- **O que foi feito:** novo `src/wands_search/text.py` com `tokenize` (remove acentos, minúsculas, quebra em tudo que não é letra ou dígito; mantém a ordem e as repetições, que o BM25 conta) e `strip_accents`, movida de `profiling.py`. `profiling.simple_tokens` passou a usar `text.tokenize` e continua devolvendo um conjunto, com o mesmo resultado de antes, então a EDA não muda. 11 testes novos em `tests/test_text.py` (75 passando).
- **Decisão (baseline):** sem stemming e sem stopwords. Decimais e frações viram tokens separados (`72.5` → `72`, `5`; `3-3/4` → `3`, `3`, `4`), do mesmo jeito nos dois lados. `36"` (query) e `36 ''` (`product_name`) dão o mesmo token `36`. **Variantes a testar no ajuste, no treino:** stemming (Snowball); decimais e frações como um token só (3.369 valores de `product_name` têm decimal e 681 têm fração); remoção de stopwords.
- **Resultado (catálogo inteiro e as 480 queries, sem `label`):**
  - Tokens por produto (mediana / p95): `product_name` 6 / 13, `product_class` 2 / 4, `category_hierarchy` 8 / 15, `product_description` 60 / 160, valores de `product_features` 78 / 165. No campo único, `product_description` e `product_features` são a maior parte do texto.
  - Vocabulário do campo único: 54.416 tokens. Queries: mediana de 3 tokens, máximo 11.
  - 33 tokens de query não existem no catálogo, a maioria erros de digitação (`ligth`, `foutains`, `pedistole`). A EDA citava 36 sem os valores de `product_features`. Uma query não tem nenhum token no catálogo: `minnestrista` (`query_id` 383); o BM25 não vai retornar nada para ela.
- **Próximo passo:** etapa 3, `retrieval.py`.

### 2026-11-08: Notebook do BM25, Etapa 1 (o texto que o BM25 vai indexar)
- **O que foi feito:** novo [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb), com a Etapa 1: um produto campo a campo, tamanho de cada campo em tokens, o que há nos valores de `product_features` e as queries de treino e validação contra o vocabulário do catálogo. Novas funções em `text.py`: `SEARCH_FIELDS`, `feature_values_text`, `product_field_texts` e `single_field_text`, que o `retrieval.py` vai usar, com 3 testes (78 passando). Executado do início ao fim.
- **Por quê:** os números da entrada anterior vinham de um comando avulso no terminal; agora o notebook os reproduz.
- **Parâmetros/seed/versões:** catálogo inteiro (sem `label`). Queries só de treino e validação (384): o texto das queries de teste não é olhado, para não influenciar escolhas.
- **Resultado:**
  - `product_features` é 50,9% dos tokens do campo único e `product_description` 38,9% (juntos, 89,8%); `product_name` é 3,9%. Campo único: mediana de 159 tokens por produto, p95 300, máximo 1.465.
  - Em `product_features`, 31,4% dos tokens são `yes`/`no` e 18,4% números; `no` tem 788.090 ocorrências. Nenhuma query de treino ou validação tem `yes` ou `no`.
  - 26 das 384 queries têm algum token fora do catálogo (erros de digitação, marcas, palavras juntas como `7qt`); só `minnestrista` (`query_id` 383, validação) não tem nenhum.
- **Correção:** a entrada "Processamento de texto" citava 33 tokens fora do catálogo nas 480 queries, incluindo as de teste. O número de referência passa a ser o do notebook, só com treino e validação.
- **Variantes registradas para o ajuste (no treino):** retrieval por campo; remover `yes`/`no` ou trocar `chave : yes` pela chave; remover valores só numéricos; `product_features` fora do campo único. Correção ortográfica só se a análise de erros pedir.
- **Próximo passo:** Etapa 2 do notebook, índice `bm25s` e busca (`retrieval.py`).

### 2026-11-08: Índice BM25 e busca (etapa 3 do BM25)
- **O que foi feito:** dependência `bm25s` 0.3.16 adicionada (`uv add bm25s`). Novo `src/wands_search/retrieval.py`: `prepare_query` (validação da query), `BM25Index` (índice sobre um texto por produto, com `scores` para todos os produtos e `search` com os K primeiros) e `build_single_field_index` (baseline). 20 testes novos em `tests/test_retrieval.py`, incluindo a nota de um exemplo calculada pela fórmula (98 passando). Etapa 2 de [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb): custo de indexação, dois exemplos de treino com `label`, entradas inválidas e latência. Executado do início ao fim.
- **Parâmetros/seed/versões:** `k1 = 1.2`, `b = 0.75`, variante `lucene` (padrão do `bm25s`, sem o fator `k1 + 1`, que não muda a ordem). Empates desfeitos pelo menor `product_id`. Limites da query: 500 caracteres e 32 tokens, com corte em vez de erro. Um token repetido na query conta a cada ocorrência (comportamento do `bm25s`). O teste não foi usado: exemplos e latência só com queries de treino e validação.
- **Entradas inválidas:** não texto, vazia ou só espaços geram `InvalidQueryError`; só caracteres especiais ou sem token no catálogo retornam lista vazia; query longa é cortada (`truncated = True`). Escrita não latina e emoji são descartados pela tokenização (só letras e dígitos ASCII).
- **Resultado:**
  - Indexação de 10 a 11 s em três execuções (tokenização é o passo mais lento); 4.150.707 pares (token, produto); 33,6 MB em memória; vocabulário de 54.417 tokens (inclui o token vazio do `bm25s`).
  - Latência do retrieval com K = 100: abaixo de 1 ms no p50 e entre 2,5 e 3,5 ms no p95, em três execuções, macOS x86_64.
  - Exemplos de treino: em `tye dye duvet cover` (`tye` fora do catálogo), 5 dos 10 primeiros são Exact; em `pedistole sink`, só `sink` conta, e os 10 primeiros são acessórios de pia (5 Irrelevant, 5 sem `label`), com notas quase empatadas.
- **Próximo passo:** etapa 4, `evaluate.py` (avaliação por query, bootstrap, latência, bloqueio do teste), e a Etapa 3 do notebook com o BM25 na validação.

### 2026-11-08: Avaliação do BM25 baseline (etapa 4)
- **O que foi feito:** novo `src/wands_search/evaluate.py`: `load_split`, `split_queries` (o teste só abre com `allow_test=True`; sem isso, `TestSetLockedError`), `run_system` (rankings e latência por query, com 20 buscas de aquecimento), `evaluate_system`, `summary_table` (média, intervalo de 95% e n de cada métrica; p50 e p95 da latência) e `paired_bootstrap`. `bootstrap_mean_ci` foi movida de `profiling.py` para `metrics.py`; `profiling` continua expondo a função para a EDA. 11 testes novos (109 passando). Etapa 3 de [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb), executado do início ao fim. Resultados na tabela do [EVALUATION.md](EVALUATION.md).
- **Parâmetros/seed/versões:** BM25 do campo único, `k1 = 1.2`, `b = 0.75`, `lucene`, `bm25s` 0.3.16. Cada sistema devolve 200 produtos (Capped Recall@200). Bootstrap com 2.000 sorteios e `BOOTSTRAP_SEED = 0`. O teste não foi usado.
- **Resultado:**
  - NDCG@10: 0,700 no treino [0,665; 0,736] e **0,620 na validação [0,555; 0,687]**. MRR@10 (Exact): 0,700 e 0,610. Capped Recall@100 (Exact): 0,697 e 0,702; na validação, 0,611 em @50 e 0,771 em @200.
  - judged@10 de 0,815 no treino e 0,756 na validação; sem os produtos sem `label`, o NDCG@10 subiria 0,121 [0,098; 0,145] e 0,161 [0,116; 0,209]. A regra "sem `label` = 0" só pode ser confirmada com um segundo sistema.
  - Checagem da estratificação: correlação de postos entre o NDCG@10 por query e `exact_share` de 0,152; com `n_judged` 0,085; com a fração de Irrelevant 0,022. A estratificação fica como está.
  - A validação tem mais queries com nota perto de 0 que o treino (cerca de 8% contra 4% entre 0 e 0,05).
  - As 10 piores queries de treino têm NDCG@10 = 0; em 7 delas, nenhum dos 10 primeiros tem `label`. Hipóteses a conferir na análise de erros: `bed side table` contra `bedside`/`nightstand`; `oriental vanity`.
- **Correção:** a primeira versão da conclusão 3.1 dizia que o MRR@10 de 0,61 correspondia ao primeiro Exact "perto da posição 1,6". Está errado: a média de 1/posição não se converte numa posição média. Corrigido antes do registro.
- **Próximo passo:** ajuste no treino (`k1`, `b` e variantes do texto indexado), com grade fixada antes, e uma única rodada na validação com a combinação escolhida.

### 2026-11-08: Métrica do ajuste do BM25
- **Decisão:** o ajuste no treino escolhe a combinação de maior Capped Recall@100 (só Exact, 227 queries), com desempate pelo NDCG@10 quando a diferença for menor que 0,005. Substitui o "maior NDCG@10" registrado antes no [EVALUATION.md](EVALUATION.md).
- **Por quê:** no sistema final, o BM25 gera os candidatos do reranker; um Exact na posição 80 ainda pode subir, mas um na posição 150 está perdido. O critério de seleção entre sistemas continua o NDCG@10 na validação.
