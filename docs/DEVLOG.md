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

### 2026-11-08: BM25 v2 (texto limpo e plurais) e ajuste no treino
- **O que foi feito:** BM25 v2 definida antes de qualquer número e registrada no [EVALUATION.md](EVALUATION.md): remoção de plural nos dois lados e, em `product_features`, remoção dos valores `yes`/`no` e só numéricos. Sem ablação de cada mudança, por restrição de tempo (escolha e alternativas na Etapa 4 de [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb)). Código: `text.s_stem`, `tokenize(stem=...)`, `is_droppable_feature_value`, `feature_values_text(clean=...)`, `product_field_texts(clean_features=...)`; `retrieval` com `stem` no índice e na query, `single_field_tokens`, `BASELINE_TEXT` e `V2_TEXT`; `evaluate.tune_bm25` e `select_tuned`. 139 testes passando.
- **Decisão de implementação:** o S-stemmer de Harman (1991) transforma `mattresses` em `mattresse`, que não bate com `mattress`; cerca de 1.000 valores de `product_class` têm esse tipo de plural (`benches`, `boxes`, `mattresses`). Acrescentamos uma regra nossa: *-es* depois de *ss*, *x*, *z*, *ch*, *sh* é removido. Efeito colateral conhecido: `niches` → `nich`.
- **Parâmetros/seed/versões:** grade `k1` {0,6; 0,9; 1,2; 1,5; 2,0} × `b` {0,3; 0,5; 0,75; 0,9} no treino, escolha por Capped Recall@100 com desempate por NDCG@10 (tolerância 0,005). Bootstrap pareado com 2.000 sorteios, seed 0. O teste não foi usado.
- **Resultado:**
  - Texto indexado 24,5% menor na mediana (159 → 120 tokens por produto); vocabulário 11,5% menor.
  - Escolhida `k1 = 1.2`, `b = 0.5`. Diferenças pequenas entre combinações (Capped Recall@100 de treino de 0,715 a 0,736), mas 12 das 19 são piores que a escolhida com intervalo pareado que exclui 0. No treino, a mudança de texto pesa mais que `k1` e `b` (0,697 → 0,726 com os valores padrão).
  - Validação, v2 × baseline: NDCG@10 0,653 contra 0,620 (+0,033 [0,014; 0,056]); MRR@10 +0,051 [0,013; 0,093]; Capped Recall@50 +0,041 [0,018; 0,063]; Capped Recall@100 +0,003 [−0,047; 0,046]. A v2 melhora a ordem dentro dos 100, mas não a cobertura.
  - Condensed NDCG@10 +0,018 [−0,007; 0,044]: a regra "sem `label` = 0" não inverte a comparação, mas parte do ganho vem de mais produtos julgados no topo.
- **Próximo passo:** retrieval semântico (vetorial) e híbrido, para aumentar a cobertura dos 100 candidatos.

### 2026-11-08: Intervalos de 95% como saída do notebook do BM25
- **O que foi feito:** as diferenças com intervalo de 95% passaram a ser saídas do notebook, não só texto das conclusões. Etapa 4.2: tabela com a diferença pareada de cada combinação da grade contra a escolhida (Capped Recall@100 e NDCG@10, treino). Etapa 4.3: tabela com cada métrica do baseline e da v2 com intervalo e a diferença pareada com intervalo, e um gráfico das diferenças. Novas funções: `evaluate.compare_systems`, `evaluate.format_ci`, `plots.difference_plot`; `evaluate.tune_bm25` passou a devolver também as métricas por query de cada combinação. 142 testes passando.
- **Correção:** as conclusões diziam "grade quase plana". Com os intervalos pareados, as diferenças são pequenas (até −0,016 de Capped Recall@100), mas 12 das 19 combinações são piores que a escolhida com intervalo que exclui 0. Texto corrigido no notebook, no DEVLOG e no EVALUATION.

### 2026-11-08: Revisão de legibilidade da EDA (cópia `01_eda_revised.ipynb`)
- **O que foi feito:** cópia [notebooks/01_eda_revised.ipynb](../notebooks/01_eda_revised.ipynb) do notebook da EDA, reescrita para ser lida sem o código e sem ler as células anteriores. O original `01_eda.ipynb` não mudou. Mudanças:
  - Toda tabela tem título e, quando precisa, uma nota que define as colunas. Nova função `plots.table` (título, nota, arredondamento e corte de textos longos), com 3 testes (145 passando). Os blocos de `print` que funcionavam como tabela viraram tabelas com título.
  - Conclusões em formato fixo e mais curto: Resultados, Suposições, Limitações e Escolhas e alternativas (em tabela, com o status de cada escolha: decidida, proposta ou em aberto).
  - "Suposições" agora só traz o que tomamos como verdadeiro sem verificar, com o que muda se for falso. Descrições do método e limitações da medição, que estavam como suposições, foram para "Limitações" ou para o texto antes da célula.
  - Referências vagas ("como assumido acima", "pergunta da Etapa 1", "a proposta") foram trocadas pelo conteúdo explícito e pela etapa exata. Subetapas numeradas (2.3.1, 2.5.1, 2.5.2).
  - Termos técnicos em inglês (label, token, split, train/validation/test set, stratification, data leakage, pooling bias, null, imputation, typo etc.), reunidos numa nova tabela "Termos usados no notebook". "Rating" passou a designar só as colunas de opinião dos clientes, e "avaliação" só a avaliação do sistema. Tamanhos medidos com `str.split` são chamados de palavras, e não de tokens.
  - Nomes de variáveis consistentes e sem reuso (`raw_labels` e `labels`, `query_profile`, `query_split`, `SETS`, `pair_ratings`, `has_ratings` em vez de `has_ratings_flag`, entre outros).
- **Parâmetros/seed/versões:** os mesmos do notebook original. Notebook executado do início ao fim; todos os números das conclusões conferidos com as novas saídas, e nenhum mudou. O teste não foi usado.
- **Próximo passo:** o usuário decide se a cópia substitui o original.

### 2026-11-08: Retrieval vetorial e híbrido: decisões, código e testes
- **O que foi feito:** decisões do vetorial e do híbrido registradas no [EVALUATION.md](EVALUATION.md) antes de qualquer número ("Retrieval vetorial e híbrido"). Código: `embeddings.py` (`FastEmbedEncoder`, `DenseIndex` com busca exata por cosseno, cache dos vetores em `cache/`), `retrieval.rrf_fuse` e `retrieval.HybridRetriever`, `evaluate.evaluate_grid`, `text.SHORT_TEXT_FIELDS` (e `single_field_text` passa a pular campos vazios, sem mudar os tokens do BM25). Testes com um encoder falso, sem baixar o modelo: 173 passando.
- **Decisões:** `BAAI/bge-small-en-v1.5` pré-treinado, sem fine-tuning, por restrição de tempo; `fastembed` porque `torch` não instala no macOS x86_64 com Python 3.13 (`onnxruntime` limitado a < 1.24 só nessa plataforma, porque as versões novas não têm build para ela); grade no treino de texto curto ou longo × com ou sem prefixo de query; RRF com k = 60 fixo, sem ajuste (pode ser ajustado depois, no treino, como nova decisão); query sem tokens não retorna nada, como no BM25.
- **Medido antes da grade (custo, não qualidade):** tokens por produto no tokenizer do modelo: texto curto com mediana de 27 e máximo de 82; texto longo com mediana de 154 e 0,6% acima de 512. Em 1.000 produtos, gerar os embeddings do texto longo levou 125 s com batches na ordem original e 48 s com batches ordenados por comprimento (menos padding), com embeddings idênticos (cerca de 35 min estimados para o catálogo). O embedding de uma query leva cerca de 5 ms.
- **Próximo passo:** notebook `03_vector_hybrid.ipynb`: indexação, latência, entradas inválidas e a grade no treino.

### 2026-11-08: BM25 v3 (chave dos valores `yes`)
- **O que foi feito:** pedido de testar a v2 mantendo a informação dos valores `yes` de `product_features`: um par `chave : yes` entra pelo texto da chave (`upholstered : yes` vira `upholstered`). Regra registrada no [EVALUATION.md](EVALUATION.md) antes de rodar. Código: `text.feature_values_text(yes_keys=...)`, `product_field_texts(yes_keys=...)`, `retrieval.V3_TEXT`; 2 testes novos. Etapa 5 de [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb).
- **Resultado:**
  - Antes de rodar, sem `label`: 363.512 pares `yes`, 2.887 chaves, a maioria de garantia e conformidade com palavras emendadas; só 9,2% das ocorrências de tokens das chaves coincidem com tokens de queries de treino ou validação.
  - Ajuste no treino escolheu a mesma combinação da v2 (`k1 = 1.2`, `b = 0.5`).
  - Validação, v3 − v2: NDCG@10 +0,002 [−0,004; 0,009], Capped Recall@100 +0,005 [−0,009; 0,025]; todos os intervalos incluem 0.
- **Decisão:** a v2 continua como BM25 de referência (mais simples, pela regra de seleção).
- **Observação:** outra sessão trabalhou no repositório ao mesmo tempo (`embeddings.py`, `plots.table`, `notebooks/01_eda_revised.ipynb`, `evaluate.evaluate_grid`, dependências `fastembed` e `onnxruntime`). Esta entrada cobre só a v3.

### 2026-11-08: Revisão de legibilidade do notebook do BM25 (cópia `02_bm25_revised.ipynb`)
- **O que foi feito:** cópia [notebooks/02_bm25_revised.ipynb](../notebooks/02_bm25_revised.ipynb) de `02_bm25.ipynb`, com as mesmas regras e os mesmos termos da revisão da EDA (`01_eda_revised.ipynb`). O original não mudou. Mudanças:
  - Novo TL;DR, tabela "Termos usados no notebook" e tabela de métricas. As tabelas têm título e nota (`plots.table`), e as grades de `k1` × `b` ganharam rótulos `k1 = ...` / `b = ...`.
  - Conclusões no formato Resultados / Suposições / Limitações / Escolhas e alternativas (em tabela, com status). Condições de medição (uma máquina, um exemplo, intervalos sem correção para comparações múltiplas) saíram de "Suposições" e foram para "Limitações"; hipóteses da error analysis ganharam seção própria.
  - Termos: train/validation/test set no lugar de treino/validação/teste e "parte"; tuning, ablation, error analysis, typo, field, single field, key:value pair, paired bootstrap; `irrelevant_share` no lugar de `irrelevant_fraction`; `no label` no lugar de `unjudged`.
  - Variáveis: `query_split` (a Series de `evaluate.load_split`), `baseline_index`, `baseline_per_query`, `v2_tuning`, `v2_chosen_key`, `v2_validation_per_query`, `train_validation_queries`, `query_profile`, `key_value_pairs`, `METRICS`, entre outras. Imports concentrados no Setup.
- **Correções:** três conclusões do original contradiziam a própria saída: a indexação "de 10 a 12 s, com a tokenização como passo mais lento" (a tabela mostrava 21,9 s, com o índice como passo mais lento), a latência "abaixo de 1 ms no p50 e de 5 ms no p95" (1,67 e 6,04 ms) e o tuning "de cerca de 70 s" (139 s). Na cópia, esses números são lidos da execução salva. A afirmação de que a latência da v2 "não muda" foi trocada por "mesma ordem de grandeza": em três execuções, o p95 da v2 no validation set foi de 3,3 a 9,1 ms, e o do baseline de 5,2 a 6,9 ms.
- **Parâmetros/seed/versões:** os mesmos do original. Notebook executado do início ao fim; reexecutar refaz a mesma rodada determinística no validation set, sem nova escolha. Métricas idênticas às do original. O test set não foi usado.
- **Próximo passo:** o usuário decide se a cópia substitui o original.

### 2026-11-08: Regras de formato dos notebooks no CONTRIBUTING
- **O que foi feito:** as regras usadas nas cópias revisadas (`01_eda_revised.ipynb` e `02_bm25_revised.ipynb`) foram registradas no [CONTRIBUTING.md](../CONTRIBUTING.md): estrutura do notebook, seções autocontidas, formato fixo das conclusões (Resultados, Suposições, Limitações, Escolhas e alternativas), tabelas com `plots.table`, conferência dos números com as saídas, tempos lidos da execução salva, termos técnicos em inglês e nomes de variáveis comuns a todos os notebooks. As duas cópias passam a ser os modelos de formato.

### 2026-11-08: Semantic search: notebook 03 e tuning no train set
- **O que foi feito:** embeddings dos 42.994 produtos gerados para os dois textos (curto em 4,6 min, longo em 31,8 min, no CPU, fora do notebook) e salvos em `cache/embeddings/`. Notebook [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb), no formato dos notebooks revisados: Etapa 1 (os dois textos, em wordpieces), Etapa 2 (custo, entradas inválidas, latência) e Etapa 3 (tuning no train set, referência contra a BM25 v2 no train set, três exemplos). Código: `FastEmbedEncoder.with_query_prefix` e `wordpiece_counts`, `plots.WORDPIECE_DEFINITION`.
- **Terminologia:** "wordpiece" para os pedaços do tokenizer do embedding model, porque "token" é só o resultado de `text.tokenize` (CONTRIBUTING).
- **Resultado:**
  - Texto longo: mediana de 154 wordpieces; 238 produtos (0,55%) passam de 512 e são cortados. Texto curto: mediana de 27.
  - Escolhido o texto longo com prefixo (Capped Recall@100 de treino 0,708, NDCG@10 0,739). O texto curto traz menos Exact (−0,028 a −0,037, intervalos que excluem 0); o prefixo ajuda pouco.
  - Referência no treino, contra a BM25 v2: nenhuma diferença com intervalo que exclui 0, mas cada sistema é melhor em queries diferentes (Capped Recall@100: semantic melhor em 25,6% das queries, BM25 v2 em 36,6%). judged@10 parecido (0,828 contra 0,821).
  - Latência na execução salva: 7,6 ms no p50, dois terços no embedding da query.
  - O validation set e o test set não foram usados.
- **Próximo passo:** a semantic search escolhida no validation set, uma única vez, contra a BM25 v2; depois a hybrid search com RRF (k = 60).

### 2026-11-08: Semantic search no validation set
- **Decisão registrada antes dos números ([EVALUATION.md](EVALUATION.md)):** o retrieval que fornece os candidatos do reranker é o de maior Capped Recall@100 no validation set entre BM25 v2, Vetorial e Híbrido, preferindo o mais simples quando o intervalo pareado inclui 0. O NDCG@10 continua sendo o critério da seleção final.
- **O que foi feito:** Etapa 4 de [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb): uma rodada da semantic search escolhida no treino (texto longo com prefixo) no validation set, contra a BM25 v2, com paired bootstrap; NDCG@10 separado por queries com e sem Exact; as queries com maior ganho e maior perda. Notebook executado do início ao fim; os tempos citados são da execução salva.
- **Resultado:**
  - NDCG@10 0,725 contra 0,653 da BM25 v2 (+0,072 [0,029; 0,116]); MRR@10 igual (0,661); Capped Recall@100 0,678 contra 0,705 (−0,027 [−0,068; 0,017]). A semantic search ordena melhor o topo, mas não cobre mais Exact nos 100 candidatos.
  - O ganho de NDCG@10 aparece nas 77 queries com Exact (+0,056 [0,018; 0,096]), não só nas 20 sem Exact.
  - Os sistemas são complementares: a semantic search ganha em queries descritivas (`brushed gold wall decor`), a BM25 v2 em queries com nome próprio (`trinaic towel rod`, `gracie oaks 62 oller 14 ceiling fan`).
  - Produtos sem `label`: o vetorial traz mais produtos julgados ao topo (judged@10 +0,050) e continua à frente no condensed NDCG@10 (+0,037 [0,006; 0,070]); a regra "sem `label` = 0" não inverte a comparação.
  - Latência: cerca de 8 ms (p50) contra cerca de 1 ms da BM25 v2.
  - O test set não foi usado.
- **Próximo passo:** hybrid search (RRF, k = 60): sobreposição dos 100 primeiros e Capped Recall@100 da união; uma rodada no validation set; escolha do retrieval dos candidatos do reranker.

### 2026-11-08: Hybrid search: diagnóstico e peso no train set
- **Decisão registrada antes dos números ([EVALUATION.md](EVALUATION.md)):** weighted RRF, w / (60 + posição na BM25 v2) + (1 − w) / (60 + posição no vetorial), com w em {0,2; 0,35; 0,5; 0,65; 0,8} escolhido no treino pela regra de sempre (Capped Recall@100, desempate por NDCG@10). Motivo: a pergunta de qual peso dar a cada lista; o RRF padrão fixa 50/50.
- **O que foi feito:** pesos em `retrieval.rrf_fuse` e `HybridRetriever`; `metrics.union_capped_recall_at_k` (teto da união); 10 testes novos (185 passando). Etapa 5 de [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb): overlap e teto da união no treino, grade de w no treino, conferência de que a fusão sobre listas guardadas reproduz o `HybridRetriever`.
- **Resultado (treino):**
  - Overlap médio de 46,9 produtos nos 100 primeiros; teto de Capped Recall@100 da união 0,818 (100 primeiros de cada) e 0,892 (200 primeiros), contra 0,731 da BM25 v2.
  - Escolhido w = 0,5, o RRF padrão: Capped Recall@100 0,754, NDCG@10 0,763. Todos os outros pesos perdem em Capped Recall@100 com intervalo que exclui 0.
  - Referência (otimista): o híbrido supera a BM25 v2 (+0,023 em Capped Recall@100, +0,041 em NDCG@10) e o vetorial (+0,046 e +0,024), todos com intervalo que exclui 0.
  - O validation set não foi usado para o híbrido; o test set não foi usado.
- **Próximo passo:** o híbrido com w = 0,5 uma única vez no validation set; escolha do retrieval dos candidatos do reranker pelo Capped Recall@100.

### 2026-11-08: Hybrid search: k e w juntos no train set
- **Decisão registrada antes dos números ([EVALUATION.md](EVALUATION.md)):** grade conjunta de k em {10, 30, 60, 100} × w em {0,2; 0,35; 0,5; 0,65; 0,8}, no treino, substituindo o k = 60 fixo e a grade só de w (que fica como histórico).
- **O que foi feito:** Etapa 5.3 de [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb), sobre as listas guardadas na Etapa 5.1; `fused_train_search` passou a aceitar k.
- **Resultado (treino):** mantida a escolha k = 60, w = 0,5 (Capped Recall@100 0,754, NDCG@10 0,763). Nenhuma das outras 19 combinações é melhor com intervalo que exclui 0. Com w = 0,5, k quase não importa (0,751 a 0,754); longe de 0,5, k pequeno perde menos Capped Recall@100, mas tem o menor NDCG@10.
- O validation set não foi usado para o híbrido; o test set não foi usado.
- **Próximo passo:** o híbrido (k = 60, w = 0,5) uma única vez no validation set; escolha do retrieval dos candidatos do reranker pelo Capped Recall@100.

### 2026-11-08: Hybrid search no validation set e o retrieval dos candidatos do reranker
- **O que foi feito:** Etapa 6 de [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb): uma rodada do `HybridRetriever` (k = 60, w = 0,5) no validation set, comparada com a BM25 v2 e com o vetorial pelo paired bootstrap; aplicação da regra registrada para o retrieval dos candidatos do reranker.
- **Resultado (validação):**
  - Híbrido com o maior NDCG@10 (0,747, contra 0,653 da BM25 v2 e 0,725 do vetorial): +0,094 [0,063; 0,128] sobre a BM25 v2; +0,022 [−0,003; 0,048] sobre o vetorial, sem diferença clara.
  - Capped Recall@100: 0,714 (Híbrido), 0,705 (BM25 v2), 0,678 (vetorial). A diferença do Híbrido inclui 0 contra os dois; o ganho de cobertura sobre a BM25 v2 visto no treino (+0,023) não se confirma de forma clara (+0,008 [−0,008; 0,028]).
  - **Candidatos do reranker: BM25 v2**, pela regra (fica o mais simples quando o intervalo inclui 0). A quarta linha da tabela passa a ser "BM25 v2 + reranker".
  - A regra "sem `label` = 0" não inverte a comparação: o Híbrido fica à frente da BM25 v2 também no condensed NDCG@10 (+0,035 [0,013; 0,058]).
  - Latência: 9,4 ms (p50) nesta execução; numa execução seguinte, 13,4 ms. Varia bastante; a ordem de grandeza é de cerca de 10 ms.
  - O test set não foi usado.
- **Próximo passo:** reranker (learning-to-rank) sobre os 100 primeiros da BM25 v2; a cosine similarity do vetorial é candidata a feature.

### 2026-11-08: Regra dos candidatos do reranker substituída e análise por tipo de query
- **Decisão ([EVALUATION.md](EVALUATION.md)), depois da Etapa 6 e antes de qualquer número do reranker:** o reranker é treinado sobre os 100 primeiros da BM25 v2 e sobre os 100 primeiros do Híbrido, e a seleção final pelo NDCG@10 decide; a regra anterior (candidatos pelo Capped Recall@100) fica substituída. Motivo: Híbrido e BM25 v2 empatam na cobertura na validação (19 queries melhores, 16 piores, 42 iguais), mas o Híbrido ordena melhor; a regra anterior tratava "intervalo inclui 0" como igualdade com 77 queries. A seleção final passa a ter cinco sistemas (BM25 v2 + reranker entra).
- **Conferência:** Capped Recall@100 recalculado de forma independente bate com a biblioteca; não havia erro de cálculo.
- **O que foi feito:** `profiling.query_token_descriptors` (com teste; 186 passando). Etapa 7 de [notebooks/03_semantic_hybrid.ipynb](../notebooks/03_semantic_hybrid.ipynb): tipos de query (rare token, token fora do catalog, número, tamanho) nas 384 queries do train e do validation set; métricas por grupo; judged@100; exemplos. Conclusões da Etapa 6.2 e TL;DR atualizados.
- **Resultado (train + validation, descritivo):**
  - Semantic search contra BM25 v2: NDCG@10 +0,031 [0,011; 0,052], Capped Recall@100 −0,024 [−0,046; −0,001]. A BM25 cobre mais, a semantic search ordena melhor.
  - A maior vantagem de cobertura da BM25 v2 está nas 29 queries com número (0,844 contra 0,703; −0,140 [−0,220; −0,066]); em queries com rare token (nomes, marcas), os dois não se distinguem.
  - Hybrid search: maior NDCG@10 que a BM25 v2 em 7 de 8 grupos (intervalo que exclui 0) e Capped Recall@100 +0,019 [0,008; 0,031] nas 384 queries; nos grupos em que a BM25 é forte, não se distingue dela.
  - judged@100 (validação): 0,676 BM25 v2, 0,627 semantic, 0,669 hybrid; o Capped Recall@100 da semantic search pode estar subestimado.
  - O test set não foi usado.
- **Próximo passo:** reranker (learning-to-rank) sobre os candidatos da BM25 v2 e da hybrid search.

### 2026-11-08: Reescrita das conclusões da Etapa 7.2 e do TL;DR do notebook 03
- **Motivo:** as conclusões misturavam três comparações (semantic × BM25 v2, hybrid × BM25 v2, hybrid × semantic) e dois conjuntos de queries (validation set; train + validation), e a frase "as queries justificam a BM25" sugeria a BM25 sozinha. A leitura parecia contraditória.
- **O que mudou (só markdown, sem reexecução):** a Etapa 7.2 separa as três comparações, diz que as 384 queries são descritivas e otimistas, e explica que a cobertura hybrid × BM25 v2 (+0,019 nas 384 queries, +0,008 no validation set) vai no mesmo sentido nos dois conjuntos. O TL;DR passa a começar pela hybrid search como melhor retrieval medido, com as comparações do validation set, e diz que a BM25 fica como componente da hybrid search. Também registra que, pela regra de seleção, hybrid e semantic empatam no NDCG@10 do validation set.
- **Gráfico novo na Etapa 6.1:** os três sistemas lado a lado em cada métrica, com o intervalo de 95% do bootstrap (`plots.interval_dot_plot`, com 2 testes; `plots.SERIES_3` = `#1baf7a`, a terceira posição da paleta categórica, validada com o script da skill de visualização: passa em separação para daltonismo, mas tem contraste 2,74:1 com o fundo, por isso cada sistema tem também um formato de marcador próprio e a tabela com os mesmos valores fica logo acima). Notebook reexecutado do início ao fim; tempos citados atualizados para a execução salva.

### 2026-11-08: Plano do reranker registrado antes de qualquer número
- **O que foi feito:** decisões do reranker registradas em [EVALUATION.md](EVALUATION.md), seção "Reranker (learning-to-rank)", antes de treinar qualquer modelo. Só documentação; nenhum código e nenhum número.
- **Decisões:**
  - LambdaMART no LightGBM, `label_gain = [0, 1, 2]`, um modelo por retrieval (BM25 v2 e Híbrido). Fonte atualizada: Qin et al. (ICLR 2021) e o survey de Lucchese, Nardini e Bruch (2023), com Burges (2010) só como origem do método.
  - Exemplos de treino: os 100 primeiros candidatos de cada query de treino. Candidatos sem `label` têm duas variantes, só julgados ou ganho 0, escolhidas no treino.
  - Cinco grupos de features: retrieval, text, cross-encoder, numeric e query.
  - Cross-encoder pré-treinado `Xenova/ms-marco-MiniLM-L-6-v2`, sem fine-tuning, pelo `fastembed`, como feature e como baseline de referência fora da seleção final.
  - Tuning por GroupKFold (5 folds, `RANKER_SEED = 0`) numa grade fixa de 72 combinações por retrieval.
  - Ablations sem cada grupo e sem as colunas de rating, só na validação.
- **Próximo passo:** tabela de candidatos do train set (`ranking.py` + testes), com a contagem de candidatos com e sem `label`.

### 2026-11-08: Reranker, Etapa 2: tabela de candidatos do train set
- **O que foi feito:**
  - `systems.py` monta a BM25 v2, a semantic search e a hybrid search com os parâmetros escolhidos no treino, que antes ficavam só nas células do notebook 03.
  - `ranking.py` tem três funções: `candidate_table` (100 primeiros por query, com `label` e ganho), `training_examples` (variantes `drop` e `zero` para candidatos sem `label`) e `rerank` (reordena os 100 primeiros e mantém o resto na ordem do retrieval).
  - 13 testes novos; 199 passando.
- **Conferência:** NDCG@10 de treino de 0,721 (BM25 v2) e 0,763 (Híbrido), iguais aos registrados.
- **Resultado (287 queries de treino, 100 primeiros candidatos):**
  - BM25 v2: 28.438 candidatos, dos quais 22,5% Exact, 43,2% Partial, 4,7% Irrelevant e 29,6% sem `label`. Seis queries trazem menos de 100 produtos.
  - Híbrido: 28.700 candidatos, dos quais 23,1% Exact, 45,0% Partial, 4,2% Irrelevant e 27,6% sem `label`.
  - A fração sem `label` cresce com a posição: de 18% (BM25 v2) e 14% (Híbrido) nos 10 primeiros para 36% e 35% nas posições 51 a 100.
  - Ficam fora do treino 5 queries (BM25 v2) e 4 (Híbrido) sem nenhum candidato Exact ou Partial.
  - Os dois conjuntos compartilham 20.541 pares (query, produto).
  - O test set não foi usado.
- **Leitura:** na variante `drop`, os únicos exemplos negativos são os Irrelevant, menos de 5% dos candidatos, e o modelo aprende quase só a separar Exact de Partial. Na variante `zero`, os produtos sem `label` viram os principais exemplos negativos.
- **Próximo passo:** features (`features.py`).

### 2026-11-08: Reranker, Etapa 3: features
- **O que foi feito:**
  - `features.py`: `FeatureBuilder` calcula as 30 features dos cinco grupos (retrieval, text, cross_encoder, numeric, query) para os candidatos de uma query. `FastEmbedCrossEncoder` envolve o cross-encoder. `FEATURE_GROUPS` define os grupos da ablation.
  - 11 testes novos; 210 passando.
  - Dependências: `lightgbm` 4.7.0, `scikit-learn` 1.9.1.
  - Detalhes da implementação em [EVALUATION.md](EVALUATION.md).
- **Resultado (train set, união dos candidatos dos dois retrievals, 36.597 pares (query, produto)):**
  - **Cross-encoder:** a mediana da nota separa bem os `label`: Exact 3,0; Partial −1,3; Irrelevant −4,9; sem `label` −8,3. Entre todas as features, é a maior diferença entre Exact e Partial.
  - **Rating:** a mediana de `rating_count` é um pouco menor nos Exact (log 2,71) que nos Irrelevant (3,22). Mais avaliações não indicam mais relevância nestes candidatos.
  - **number_match:** null em 91,6% dos pares (queries sem número). Nas queries com número, a mediana é 1,0 nos Exact e 0 nos outros `label`.
  - **Latência das features, na execução salva** (Mac Intel, CPU, uma execução): p50 de 619 ms e p95 de 1.278 ms por query, com cerca de 128 produtos. Sem o cross-encoder e com 100 produtos, p50 de 43 ms e p95 de 73 ms. O cross-encoder domina o custo.
  - O test set não foi usado.
- **Próximo passo:** tuning por GroupKFold e treino (Etapa 4).

### 2026-11-08: Capped Recall@100 com Exact e Partial no notebook 03
- **Motivo:** a métrica secundária do protocolo era calculada por query (`metrics.query_metrics`), mas ficou fora da lista `METRICS` do notebook 03 e da tabela do [EVALUATION.md](EVALUATION.md).
- **O que foi feito:** `capped_recall@100_exact_partial` entrou em `METRICS` (tabelas, comparações pareadas e gráficos das Etapas 3, 4, 5 e 6) e na tabela de métricas do notebook; notas de tabelas e gráficos corrigidas; notebook reexecutado. Nenhuma regra de escolha usa a métrica, então nenhuma decisão muda.
- **Resultado (validação):** BM25 v2 0,661; Vetorial 0,660 (−0,001 [−0,033; 0,033]); Híbrido 0,694, acima dos dois com intervalo que exclui 0 (+0,033 [0,015; 0,052] e +0,034 [0,015; 0,052]). Com Partial também relevante, a vantagem de cobertura do Híbrido sobre a BM25 v2 aparece com clareza; só com Exact (Etapa 6.1), não.
- **Latência:** uma das execuções desta etapa rodou com a máquina ocupada (Vetorial com p50 de 13,5 ms, contra 7,3 a 8,2 ms nas outras); as faixas do EVALUATION.md passam a separar as duas condições.

### 2026-11-08: Reranker, Etapa 4: tuning por GroupKFold no train set
- **O que foi feito:**
  - `reranker.py`: treino do LambdaMART (LightGBM), folds por query, `cross_validate`, `summarize_cv`, `select_combination` e `rerank_run`.
  - 7 testes novos; 217 passando.
  - Rodados 72 combinações × 5 folds nos dois retrievals, cerca de 12 minutos no total. As features dos 36.597 pares levam cerca de 2 minutos, quase todo o tempo no cross-encoder.
  - Decidido antes de qualquer número: a latência não entra na regra de seleção, porque depende da máquina ([EVALUATION.md](EVALUATION.md)).
- **Resultado (fora do fold, 287 queries de treino):**
  - Configuração escolhida nos dois retrievals: `zero`, 15 folhas, `learning_rate` 0,1, 100 árvores.
  - NDCG@10: BM25 v2 de 0,721 para 0,784; Híbrido de 0,763 para 0,794.
  - **A `zero` vence no NDCG@10 e a `drop` no condensed NDCG@10.** O ganho da `zero` acompanha o judged@10 (+0,06 a +0,08). No Híbrido, a `zero` não melhora o condensed NDCG@10 (−0,007 [−0,016; 0,002]) nem o MRR@10, e a `drop` não melhora nada.
  - Leitura e números completos em [EVALUATION.md](EVALUATION.md).
  - O validation set e o test set não foram usados.
- **Próximo passo:** conferir à mão, no train set, os produtos sem `label` que a `zero` tira do topo e os que ela põe no topo; depois, a validação (Etapa 5).

### 2026-11-08: Reranker: comparações extras registradas e conferência manual dos produtos sem `label`
- **Registrado antes da validação ([EVALUATION.md](EVALUATION.md)):** baseline pointwise (LightGBM com `objective = regression`, mesma configuração) e ablation sem as features de embedding (`features.EMBEDDING_FEATURES`). Código e 2 testes; 219 passando.
- **Conferência (Híbrido, variante `zero`, fora do fold, 287 queries de treino):**
  - Saem dos 10 primeiros 236 produtos sem `label` e entram 99; saldo de −137, cerca de 0,5 por query.
  - Mediana do `cross_encoder_score` dos produtos sem `label` que saem: −5,96, perto da dos Irrelevant que saem (−6,25) e bem abaixo da dos Partial que saem (−1,27).
- **Leitura qualitativa de 10 queries sorteadas (`seed = 0`), uma pessoa, sem `label`:**
  - Cerca de metade dos produtos sem `label` que saem está claramente fora do assunto, como um apanhador de sonhos para "day bed indian" e uma poltrona de couro para "milk cow chair".
  - A outra metade parece relevante, como "karina black outdoor wall lantern" para "outdoor light fixtures" e sofás de pátio para "modern outdoor furniture".
  - As duas explicações da Etapa 4 aparecem: o modelo tira do topo produtos fora do assunto e também produtos provavelmente relevantes que não foram julgados.
  - Contraexemplo: em "milk cow chair", o modelo põe no topo três produtos Irrelevant com "milk cow" no texto (bandeira, caneca, jarra).
- **Próximo passo:** validação (Etapa 5).

### 2026-11-08: Reranker: BM25 v2 + reranker sem features de embedding e comparações do cross-encoder
- **Decisões ([EVALUATION.md](EVALUATION.md)), antes de qualquer número de validação do reranker:**
  - A BM25 v2 + reranker usa as 25 features fora de `features.EMBEDDING_FEATURES` e não roda o modelo de embeddings na busca (`query_features(..., use_embeddings=False)`). Motivo: cada sistema é definido pelos componentes que usa, e com essas features ela seria, na prática, um sistema híbrido.
  - Ablation nova: a BM25 v2 + reranker com as features de embedding acrescentadas.
  - O ganho do cross-encoder é lido em três comparações; a nova compara os dois sistemas, ambos sem o cross-encoder.
  - Código: `features.LEXICAL_RERANKER_FEATURES` e um teste novo; 220 passando.
- **Tuning refeito (BM25 v2, 25 features, 287 queries de treino, fora do fold):**
  - Escolhida: `zero`, 15 folhas, `learning_rate` 0,1, `min_data_in_leaf` 50, 100 árvores.
  - NDCG@10 de 0,721 (ordem da BM25 v2) para 0,778 (+0,056 [0,039; 0,075]).
  - Condensed NDCG@10: −0,002 [−0,012; 0,007]. judged@10: +0,089.
  - O mesmo padrão do Híbrido.
  - O validation set e o test set não foram usados.
- **Próximo passo:** validação (Etapa 5).

### 2026-11-08: Reranker, Etapas 5 e 6: validação e ablations
- **O que foi feito:**
  - Uma execução no validation set (97 queries), com os modelos finais treinados em todo o train set nas configurações do GroupKFold.
  - Avaliados os dois rerankers, as referências (pointwise e cross-encoder sozinho), as ablations registradas, NDCG@5 e @15 como sensibilidade, e a latência do ranking.
  - Correção antes dos resultados: `rerank_run` perdia a query de validação sem resultados na BM25 v2 (`minnestrista`). O reranker seria avaliado em 96 queries e a ordem do retrieval em 97. Agora a query entra com lista vazia. Um teste novo; 221 passando. O train set não tinha esse caso.
- **Resultado:** números completos em [EVALUATION.md](EVALUATION.md).
  - BM25 v2 + reranker: NDCG@10 de 0,744 (+0,091 sobre a BM25 v2).
  - Híbrido + reranker: 0,772 (+0,025 sobre o Híbrido), o maior NDCG@10 dos cinco sistemas.
  - Nos dois, o condensed NDCG@10 não muda: o ganho vem de trazer ao topo produtos com `label`, como no treino.
  - O Híbrido + reranker supera a BM25 v2 + reranker também no condensed NDCG@10 (+0,030 [0,011; 0,050]).
  - O cross-encoder não agrega nada distinguível de 0 em nenhum dos dois sistemas e custa cerca de 250 ms por query nesta máquina.
  - LambdaMART supera o pointwise no Híbrido (+0,032 [0,009; 0,056]).
  - Os grupos numeric e query e as colunas de rating não mostram efeito.
  - O test set não foi usado.
- **Próximo passo:** decidir com o usuário a seleção final (a regra aponta o Híbrido + reranker com cross-encoder; a versão sem ele tem o mesmo NDCG@10 e é cerca de 12 vezes mais rápida, mas foi registrada fora da seleção).

### 2026-11-08: Notebook 04 do reranker
- **O que foi feito:**
  - `notebooks/04_reranker.ipynb`, no formato dos `_revised`, com sete etapas: candidatos e exemplos de treino, features, tuning por GroupKFold, validação, o que cada parte agrega, latência e seleção final. Executado do início ao fim em cerca de 20 minutos; os números do markdown foram conferidos com as saídas.
  - Funções novas no pacote, para o notebook não definir código reutilizável: `reranker.out_of_fold_scores`, `reranker.ranking_latency`, `reranker.evaluate_scores`, `features.ablation_feature_sets` e cortes extras de NDCG em `metrics.evaluate_run`. 226 testes passando.
  - README atualizado com os módulos e o notebook novos.
- **O que mudou em relação aos registros anteriores:**
  - **Conferência manual (Etapa 3.3):** o notebook sorteia outras 10 queries. Dos 23 produtos sem `label` que saem do top 10, cerca de 6 estão fora do assunto, cerca de 13 parecem relevantes (quase sempre como um Partial) e 4 são ambíguos. A parte do ganho que parece efeito do pooling bias é maior que na leitura anterior, fora do notebook.
  - **Ablations:** no hybrid search + reranker, tirar o grupo numeric baixa o condensed NDCG@10 (+0,010 [0,004; 0,017]); as colunas de rating sozinhas não têm esse efeito.
  - **Latência na execução salva** (ranking p50 / p95): 269,6 / 367,7 ms com o cross-encoder e 6,1 / 7,2 ms sem ele (BM25 v2 + reranker); 278,7 / 390,7 ms e 24,7 / 29,1 ms (hybrid search + reranker).
  - Os demais números são iguais aos do script de validação, salvo a terceira casa de alguns intervalos do bootstrap.
  - O test set não foi usado.
- **Em aberto:** levar ao test set o hybrid search + reranker com ou sem o cross-encoder (emenda proposta ao usuário).

### 2026-11-08: Emenda da regra de seleção, sistema escolhido e modelos salvos
- **Emenda ([EVALUATION.md](EVALUATION.md), "Seleção e teste"), feita depois de ver o validation set do reranker:** o princípio "fica o mais simples quando a diferença inclui 0" vale também para os componentes de um sistema. Motivo: a regra deixava de fora o cross-encoder, que entrou como grupo de features e foi medido só como ablation. Deveríamos ter exigido que ele se justificasse na seleção.
- **Sistema escolhido, registrado antes do test set: Híbrido + reranker sem o cross-encoder** (NDCG@10 de 0,776 no validation set). Pela regra, fica o Híbrido + reranker (0,772); pela emenda, a versão sem o cross-encoder, que empata com ele (−0,005 [−0,015; 0,006]) e custa uma fração da latência. O test set roda os cinco sistemas da regra mais o Híbrido + reranker com o cross-encoder, que só é reportado.
- **Modelos salvos:**
  - `wands_search.train_reranker` treina os 4 modelos finais no train set, com as combinações do GroupKFold (`reranker.CHOSEN_COMBINATIONS`), e os grava em `models/`: um `.txt` do LightGBM e um `.json` de metadados (retrieval, features na ordem, combinação, versões) por modelo. Cerca de 180 s no CPU; cerca de 180 KB por modelo.
  - `reranker.load_model` lê um modelo e confere que as features batem com os metadados.
  - O escolhido é `hybrid_reranker_no_cross_encoder` (29 features): na busca, o cross-encoder não é carregado.
- **Notebook 04, Etapa 7 reescrita:** tabela final com todos os sistemas e variantes (7.1), gráficos comparando os sistemas, por métrica e NDCG@10 contra latência (7.2), seleção com a emenda (7.3) e conferência de que os modelos salvos reproduzem os do notebook (7.4).
- **Código:** `features.candidate_features` (antes só no notebook), `plots.system_interval_plot`, `reranker.save_model`, `reranker.load_model`, `reranker.SAVED_MODELS`. 231 testes passando. README, `CONTRIBUTING.md` (pasta `models/`) e `AGENTS.md` (comando de treino) atualizados.
- O test set não foi usado.
- **Próximo passo:** busca utilizável (API ou CLI) que carrega o modelo escolhido, com tratamento de entradas inválidas; depois, error analysis, test set e nota técnica.

### 2026-11-08: Busca de ponta a ponta e notebook 05
- **O que foi feito:**
  - `search.SearchPipeline`: carrega o modelo salvo e monta só o que ele precisa, lendo os metadados (o cross-encoder só é carregado se o modelo o usar). Valida a query e o `k`, roda o retrieval (200 primeiros) e o reranker (100 primeiros) e devolve os resultados com a latência de cada etapa. 17 testes novos, num catalog de brinquedo; 248 passando.
  - `notebooks/05_search.ipynb`: buscar qualquer texto (`QUERY`), a lista antes e depois do reranker com os `label` do validation set, entradas inválidas e latência. Executado do início ao fim.
  - Preferência do usuário: notebook ou API em vez de CLI. O notebook foi feito; a API fica para depois.
- **Resultado (validation set, na execução salva):**
  - O reranker melhora o NDCG@10 de 44 das 97 queries, piora 20 e não muda 33 (média +0,029, o mesmo ganho do `04_reranker.ipynb`).
  - Maior perda, "carpet 5x6" (de 0,782 para 0,538): o top 10 passa a ter cinco chair mats Irrelevant, que têm "carpet" no nome. Hipótese para a error analysis: o reranker pesa as palavras da query no `product_name` mesmo quando o produto é de outro tipo.
  - Latência de uma busca: p50 de 38,1 ms (11,3 ms de retrieval e 26,7 ms de ranking), p95 de 45,6 ms, num CPU.
  - Carga do sistema: 43 s com os embeddings em cache.
  - O test set não foi usado.
- **Pendente:** GitHub Release dos embeddings, para que um revisor não precise gerá-los (cerca de 40 min no CPU); detalhes no `HANDOVER.md` local.

### 2026-11-09: Notebook 04 reexecutado com a Etapa 7 nova
- **Correção:** a primeira execução da Etapa 7 falhou na 7.4. Um laço do gráfico de latência usava `chosen` como variável e sobrescrevia as combinações escolhidas da Etapa 3, o reuso de nome que o `CONTRIBUTING.md` proíbe. Renomeada para `is_selected`.
- **Conferência:** todos os números de métricas do markdown batem com as saídas. Os quatro modelos salvos em `models/` dão exatamente as mesmas notas dos modelos treinados no notebook (diferença máxima de 0 em todos os candidates do validation set).
- **Latência nesta execução salva** (substitui a da execução anterior do notebook; os números variam a cada execução):
  - ranking p50 / p95: 296,4 / 414,1 ms com o cross-encoder e 7,1 / 8,1 ms sem ele (BM25 v2 + reranker); 331,2 / 452,6 ms e 26,9 / 33,3 ms (Híbrido + reranker);
  - retrieval p50: 0,7 ms (BM25), 0,9 ms (BM25 v2), 8,3 ms (semantic search) e 10,8 ms (Híbrido);
  - busca completa do sistema escolhido: cerca de 38 ms na mediana.
- O test set não foi usado.

### 2026-11-09: Capped Recall@100 com Exact e Partial no notebook 04
- **O que foi feito:** a métrica secundária `capped_recall@100_exact_partial` (Exact e Partial como relevantes, 97 queries) entra na tabela de métricas do notebook, na Etapa 4.1, na tabela final (7.1) e num quinto painel do gráfico da 7.2. Notebook reexecutado do início ao fim.
- **Resultado (validation set):** o Híbrido é o que mais cobre (0,694), contra 0,637 (BM25), 0,661 (BM25 v2) e 0,660 (semantic search). Os rerankers têm o valor do seu retrieval. As outras métricas não mudaram.
- **Latência nesta execução salva** (substitui a da entrada anterior): ranking p50 / p95 de 285,4 / 435,7 ms com o cross-encoder e 6,9 / 8,3 ms sem ele (BM25 v2 + reranker); 335,0 / 490,1 ms e 25,7 / 30,4 ms (Híbrido + reranker). Retrieval p50: 1,0 ms (BM25), 1,1 ms (BM25 v2), 8,9 ms (semantic search), 10,5 ms (Híbrido).
- O test set não foi usado.

### 2026-11-09: Test set, uma única vez
- **Pedido do usuário:** rodar o test set nas seis linhas registradas. Primeiro foi posto como Etapa 8 do notebook 04; a execução foi interrompida antes de qualquer resultado, porque reexecutaria o notebook inteiro (cerca de 25 min). O test set foi para um notebook à parte, `notebooks/06_test_set.ipynb`, que só carrega os modelos salvos (cerca de 5 min). Uma segunda execução também foi interrompida antes de qualquer resultado, para acrescentar os gráficos. Nenhum número do test set foi visto antes da execução final.
- **O que foi feito:** as seis linhas no validation set e no test set, com os modelos salvos em `models/`, sem treino nem ajuste. Métricas com intervalos, comparações pareadas contra o escolhido, validation set contra test set e latência, com quatro gráficos. No validation set, os números reproduzem a tabela final do notebook 04.
- **Resultado (95 queries, 75 com Exact):**
  - O escolhido, Híbrido + reranker sem o cross-encoder, tem o maior NDCG@10: 0,824 [0,773; 0,870].
  - Contra o Híbrido: +0,041 [0,020; 0,063], com o condensed NDCG@10 igual (−0,002) e o judged@10 maior (+0,065), o mesmo padrão do validation set.
  - Contra a BM25 v2 + reranker: +0,010 [−0,008; 0,031], que inclui 0; no validation set, a comparação correspondente excluía 0.
  - Contra a versão com o cross-encoder: +0,003 [−0,008; 0,014]. Latência do ranking: 27,1 ms contra 376,8 ms na mediana.
  - Todos os sistemas sobem do validation set para o test set (de +0,023 a +0,097), na mesma ordem, exceto que a BM25 v2 + reranker passa o Híbrido.
- **Registro:** data, resultados e seis linhas na tabela de resultados do [EVALUATION.md](EVALUATION.md). A escolha não muda.
- **Notebook 04:** a Etapa 8 foi retirada e o cabeçalho volta a dizer que o test set não é usado, apontando para o notebook 06.

### 2026-11-09: Error analysis do sistema escolhido (notebook 07)
- **O que foi feito:**
  - `notebooks/07_error_analysis.ipynb`, só no validation set (97 queries). Cada etapa diz o que é analisado, por que, como (metodologia) e o impacto.
  - `metrics.oracle_ndcg_at_k`: o melhor NDCG@10 possível com os 100 candidates, que separa a perda do retrieval da perda do ranking.
  - `error_analysis.py`, com 13 testes novos em `tests/test_error_analysis.py`:
    - etapa com a maior perda por query;
    - comparação de `query_class` com `product_class`;
    - busca de atributos em `product_features`;
    - pares de produtos quase idênticos (TF-IDF dos cinco fields).
- **Resultado (validation set):**
  - **Retrieval ou ranking:** o oracle chega a 0,933 e o sistema a 0,776. O retrieval perde 0,067, e o ranking perde 0,156 (0,186 sem o reranker). Em 39 das 49 queries com NDCG@10 < 0,9, a maior parte da perda está no ranking.
  - **Produtos sem `label`:** entre os produtos julgados do top 10 com a mesma classe da query, só 0,9% são Irrelevant. Sem os produtos sem `label`, o NDCG@10 sobe de 0,776 para 0,831. O 0,776 é provavelmente um piso.
  - **Typos:** com as 5 queries corrigidas, o sistema traz produtos que não foram julgados. O ganho de um corretor não pode ser medido com estes `label`.
  - **Pares quase idênticos (cosine ≥ 0,95):** 5,6% têm `label` diferentes, contra 34,4% de todos os pares da mesma query, e nenhum é Exact × Irrelevant.
  - **Categorias das 49 queries, com leitura de todos os fields:**
    - `unexplained_labels`: 21,1% da perda;
    - `wrong_product_type`: 20,6% (inclui "carpet 5x6", a hipótese do notebook 05);
    - `typo`: 11,5%;
    - `pooling_bias`: 10,5%;
    - `vague_query`: 10,4%;
    - `attribute_not_met`: 8,7%;
    - `proper_name`: 8,6%;
    - `compound_query`: 4,4%.
  - **`unexplained_labels`:** nenhum field explica por que os produtos mal colocados são Partial e não Exact. Fica registrado como limitação do dataset, sem hipótese sobre a causa.
- **Próximos passos sugeridos (não feitos):**
  - features do reranker que comparem o tipo de produto da query com `product_class`;
  - features de match de atributo com os key:value pairs de `product_features`;
  - corretor ortográfico.
- O test set não foi usado.

### 2026-11-09: Declaração do uso de IA e estado final do EVALUATION
- **Seção 9 da nota técnica reescrita:** ferramenta e escopo (o assistente escreveu o código, os testes, a maior parte das análises e a documentação), papel do autor, como o código e as conclusões foram revisados, e os modelos pré-treinados usados. Motivo: o enunciado pede que a declaração diga como a IA foi usada e como o código e as conclusões foram revisados. A nota continua com 3 páginas.
- **`docs/EVALUATION.md` deixa de se apresentar como rascunho:**
  - **Cabeçalho:** diz que a Versão 0 foi editada diretamente até 2026-11-08 e é o protocolo aplicado no test set; que as mudanças de regra ficaram como itens datados, e não como versões novas; e que, depois do test set, só foi acrescentado o status final dos itens em aberto.
  - **Resumo do protocolo aplicado,** no topo: split, relevância, métricas, uso de cada set, comparação, seleção, sistema escolhido e data do test set.
  - **Status em 2026-11-09** em cada item que estava como Proposta, A definir ou Pendente (deduplicação, `product_id` como unidade, média por query, nulls sem imputation, `product_class` contra a query, mesmo conjunto de candidatos, efeito dos produtos sem `label`, ablation de rating). Cada status descreve o que foi implementado e medido, e o que não foi feito.
  - O cabeçalho da tabela "Histórico de resultados" passa a listar todos os sistemas da tabela.
- **Nenhuma regra mudou** e nenhum número foi recalculado. O test set não foi usado de novo.
- **MRR@10 na nota técnica:** definido na seção 3 e citado na ressalva da seção 4: o reranker não muda o MRR@10 de forma estatisticamente significativa nos dois sets (notebooks 04 e 06). Para abrir espaço, a seção 9 ficou mais curta e a frase de reprodutibilidade da seção 2 foi encurtada. **A nota está com 4 páginas;** o corte fica para depois das próximas mudanças.
- **Limitações de código na nota técnica, sem mudar o código:**
  - A seção 6 diz que a latência do ranking inclui recalcular o embedding da query, o BM25 e a RRF, que o retrieval já calculou.
  - A seção 8 registra que a feature `number_match` ignora as dimensões de `product_features` e não casa "5x6" com "5 x 6" (query "carpet 5x6", validation set). Corrigir a feature fica como próximo passo.
  - **Motivo para não mudar o código:** os modelos salvos foram treinados com as features atuais. Mudar o cálculo de uma feature quebraria a reprodução do test set e criaria training/serving skew na busca. Uma correção teria de ser aditiva (feature e modelo novos) e só poderia ser medida no validation set.
- **Tag git `test-set-run`** no commit `80b2a17`, o da execução única do test set. Registrada no `EVALUATION.md`.
- **Custo de indexação na seção 6 da nota técnica, corrigido:**
  - Os embeddings são dois conjuntos de 66 MB: texto longo da semantic search, ~32 min, e texto curto da feature `short_cosine`, ~5 min. Fonte: `notebooks/03_semantic_hybrid.ipynb`. Total de ~37 min.
  - Um produto novo exige calcular os seus dois embeddings e reconstruir os índices BM25, porque o `bm25s` não acrescenta documentos a um índice pronto; o reranker não precisa ser retreinado.
  - O tempo de carga (43 s) passa a ser citado como da execução salva do `notebooks/05_search.ipynb`.
- **Reprodutibilidade do `notebooks/04_reranker.ipynb`, conferida:** uma cópia foi reexecutada do início ao fim, fora do repositório, e as saídas foram comparadas célula a célula com as do notebook versionado. Todas as métricas, o tuning por GroupKFold, as ablations, os baselines e as tabelas se repetiram exatamente. Só mudaram os tempos e a latência; por exemplo, o ranking do sistema escolhido foi de 25,7 / 30,4 ms (p50 / p95) para 24,8 / 29,0 ms. A execução levou 15 min. O notebook versionado não foi alterado.

### 2026-11-09: GitHub Release dos embeddings
- **Release `embeddings-v1`** em `lubepe/ml_challenge`, criado pela interface web. A tag aponta para o commit `80b2a17`. O Release tem os dois arquivos de `cache/embeddings/` (42.994 × 384, float32, normalizados, uma linha por produto na ordem de `product_id`):
  - `a69ae5a32d14c0466cb7.npy`: texto longo, usado na semantic search e na hybrid search. sha256 `17a2f137…6bda`;
  - `c22b318b1b827f635905.npy`: texto curto, usado na feature `short_cosine`. sha256 `2ef8c1e9…cfbcf`.
- **Download automático:** quando o arquivo não está em `cache/embeddings/` e o nome dele está em `embeddings.RELEASE_FILES`, `embeddings.cached_document_vectors` o baixa e confere o sha256. Se o download falhar ou o sha256 não conferir, os embeddings são gerados localmente, como antes. O nome do arquivo continua sendo a chave de cache, então texto ou modelo diferente não usa o arquivo do Release. O parâmetro `download=False` desliga o download.
- **Testes:** seis testes novos, com download simulado e sem rede; 266 testes passando neste commit. Os sha256 em `RELEASE_FILES` foram conferidos contra os arquivos locais.
- **Pendente:** o repositório ainda é privado, e por isso o download sem login retorna 404. Falta conferir o download real depois de tornar o repositório público.
- O test set não foi usado.

### 2026-11-09: README para reproduzir o projeto do zero
- **Resumo no topo:** o sistema escolhido, o NDCG@10 do test set contra o BM25 baseline e os links para a nota técnica, o EVALUATION e o DEVLOG.
- **"Reproduzir os resultados":** a ordem completa, do split à nota técnica, com o que cada passo gera, quanto tempo leva e do que depende. Inclui o aviso de que o test set já foi usado (tag `test-set-run`) e qual notebook sustenta cada seção da nota técnica.
  - Tempos medidos reexecutando cópias dos notebooks fora do repositório: `01_eda` e `01_eda_revised` ~33 s; `02_bm25` e `02_bm25_revised` ~3,4 min; `04_reranker` ~15 min (antes o README dizia ~20 min).
- **"Reprodutibilidade":** a tabela de seeds com links para as constantes, onde ficam os parâmetros e as versões, e o resultado das reexecuções. Os notebooks 01, 02 e 04 reproduzem todas as métricas exatamente; só os tempos mudam. A exceção é `queries_positive_pct` de `has_ratings` no `01_eda_revised.ipynb`: uma query com correlação igual a zero passa a ter um valor positivo minúsculo, por arredondamento de ponto flutuante. O número não é citado no texto.
- **Dataset:** origem no repositório [wayfair/WANDS](https://github.com/wayfair/WANDS) (licença MIT), com a citação do artigo (ECIR 2022). Os arquivos em `dataset/` são os do repositório, com os nomes originais. A renomeação de `label.csv` registrada na entrada de 2026-11-05 foi desfeita depois.
- **Estrutura:** a descrição de `src/wands_search/` virou uma tabela de módulos, e a dos notebooks diz que as versões `_revised` trazem os mesmos resultados com texto revisado.
- O texto sobre o download dos embeddings do Release, escrito com o commit `bea567c`, foi mantido.

### 2026-11-09: Ablation do sistema escolhido e "não distinguível de 0"
- **Ablations do sistema escolhido** (`notebooks/04_reranker.ipynb`, Etapa 5.3.1, nova). As ablations da Etapa 5.3 eram do Híbrido + reranker com o cross-encoder (0,772), e o escolhido é a versão sem ele (0,776). Repetidas sobre o escolhido, só no validation set e sem novo tuning, depois do test set. A seleção não muda.
  - Escolhido − sem o grupo (NDCG@10): text +0,043 [0,025; 0,064], embedding +0,036 [0,013; 0,060], retrieval +0,030 [0,005; 0,057]; numeric, query e rating não distinguíveis de 0.
  - Sem o cross-encoder, o grupo text pesa mais que no modelo completo (+0,043 contra +0,018).
  - Antes de substituir o notebook, uma cópia com a seção nova foi executada do início ao fim e comparada com a versão anterior: todas as métricas se repetiram exatamente, e só os tempos e a latência mudaram. O markdown das Etapas 6 e 7 foi atualizado com as latências da nova execução (ranking do escolhido: 24,8 / 28,9 ms, antes 25,7 / 30,4 ms), e o TL;DR cita a Etapa 5.3.1.
  - A célula de conclusões da importância por gain apontava a ablation como "Etapa 5.1"; corrigido para 5.3.
- **"Empate" → "não distinguível de 0":** um intervalo de 95% que contém 0 não mostra que os sistemas são iguais, só que a amostra não os separa. Trocado na nota técnica (definição na seção 3, regra de escolha e seções 4, 5 e 8) e no markdown dos notebooks 03 e 04, sem reexecução. O texto histórico da emenda no `EVALUATION.md` não foi alterado. "Desempate" e "empate" no sentido de valores iguais continuam.
- **Nota técnica:**
  - a seção 5 passa a citar as ablations do escolhido (0,733 sem text, 0,740 sem embedding, 0,746 sem retrieval);
  - "a popularidade do produto não pesa" virou "não mostrou efeito mensurável nestes julgamentos";
  - a seção 8 ganhou o item "Comparações múltiplas": o test set confirma a melhora do reranker sobre a hybrid search, mas não a vantagem do escolhido sobre o BM25 v2 + reranker;
  - contagem de testes atualizada para 270. A nota continua com 4 páginas, a cortar no fim.
- **`EVALUATION.md`:** ablations do escolhido registradas como resultado posterior ao test set; latência do escolhido na tabela de resultados atualizada para a execução salva atual, com a anterior entre parênteses.
- 270 testes passando.

### 2026-11-09: Correção de autoria das leituras qualitativas
- **Correção:** as leituras qualitativas dos notebooks foram feitas pelo assistente de IA, sem revisão humana. Os textos que diziam "uma pessoa", "à mão", "lemos" ou "nossa" passam a dizer isso explicitamente:
  - `notebooks/04_reranker.ipynb`, Etapa 3.3 e TL;DR: a leitura dos produtos sem `label` de 10 queries do train set, e a "leitura anterior, fora do notebook", que não tem registro;
  - `notebooks/07_error_analysis.ipynb`: as correções de typo (Etapa 3), as categorias de erro das 49 queries (Etapa 5) e as regras de atributo por query;
  - a entrada "Leitura qualitativa de 10 queries sorteadas (`seed = 0`), uma pessoa, sem `label`", mais acima neste DEVLOG, também foi feita pelo assistente. A entrada fica como está, e esta a corrige;
  - nota técnica, seção 7: as categorias de erro e as correções de typo são do assistente, numa única leitura.
- Só markdown; nenhum notebook foi reexecutado.

### 2026-11-10: Trabalhos futuros
- **`docs/EVALUATION.md`, seção nova "Trabalhos futuros":** seis itens em ordem de prioridade, cada um com o problema visto nos dados, a proposta, como medir e os riscos:
  1. medir quanto do ganho do reranker é real, com um juiz (pessoa ou LLM) validado nos pares que já têm `label` e o NDCG@10 recalculado; inclui a alternativa sem juiz (todos os sem `label` como Irrelevant e como Partial);
  2. tipo de produto da query contra `product_class`;
  3. atributos de `product_features`;
  4. a correção de `number_match`;
  5. fine-tuning do embedding model;
  6. corretor ortográfico.
  - **Riscos registrados, entre outros:** o juiz vê só o texto, a circularidade entre o LLM e as features do reranker, overfitting do classificador de tipo e do fine-tuning pelo tamanho do train set (287 queries), negativos falsos por pooling bias e ganhos pequenos demais para medir em poucas queries.
  - A "parte da perda" de cada categoria é tratada como teto, e não como ganho esperado.
- **Nota técnica:**
  - seção 4: a leitura de 10 queries do train set (feita pelo assistente de IA) entra na ressalva: cerca de um quarto dos produtos sem julgamento que o reranker tira do topo estava fora do assunto, e mais da metade parecia relevante;
  - seção 8: os próximos passos viram uma lista em ordem de prioridade, com o detalhe no `EVALUATION.md`.

### 2026-11-10: TL;DR do notebook 01 revisado
- **`notebooks/01_eda_revised.ipynb`, TL;DR** (só markdown, sem reexecução):
  - o item sobre palavras da query diz o que o 42% mede (média por par julgado, em `product_name`, `product_class` e `category_hierarchy`) e que as palavras em comum não bastam nem para o retrieval nem para o ranking; a Etapa 5.1 ganhou o item correspondente sobre o retrieval;
  - novo item: um `product_id` parece reunir vários SKUs, com os números das Etapas 2.5.1 e 2.5.2; SKU entrou na tabela de termos;
  - o split cita as duas variáveis de stratification (`n_judged` e `exact_share`);
  - o item de métricas fica só com o que o notebook 01 decide: NDCG@10 principal em 479 queries; Capped Recall@100 e MRR@10 só com Exact, em 379. As regras de ajuste do retrieval e do reranker, decididas nos notebooks 02 a 04, saíram do TL;DR.

### 2026-11-10: Limitação do foco no top 10
- **Nota técnica, seção 8, item novo "Foco nos 10 primeiros":** o reranker é treinado com `lambdarank_truncation_level = 10` e escolhido pelo NDCG@10, e o retrieval é ajustado pelo Capped Recall@100 só com Exact, que não olha a ordem. Nenhuma métrica usada nas decisões mede as posições 11 a 100. Alternativas: NDCG@50 ou NDCG@100 e o Capped Recall@100 com Exact e Partial com mais peso na escolha. PDF regerado; a nota continua com 4 páginas.
- **`docs/EVALUATION.md`, "Trabalhos futuros", item 7 novo: avaliar e escolher também além do top 10.** Proposta: (a) NDCG@50 e NDCG@100, com judged@50 e judged@100, sobre as listas que já existem; (b) reranker com truncamento maior; (c) regra de escolha com peso também para um corte maior e para o Capped Recall@100 com Exact e Partial. Riscos: pooling bias maior em cortes maiores, peso de cada corte sem dado de uso e regra nova só para escolhas futuras. Fica fora da ordem de prioridade dos itens 1 a 6, porque muda o critério de avaliação, e não o sistema.
- **Nota técnica, seção 8:** o item 7 entra também na lista de próximos passos. A nota está com 4 páginas; o corte para 3 fica para a revisão final.

### 2026-11-10: Popularidade no topo do sistema escolhido
- **O que foi feito:** Etapa 6 nova em [notebooks/07_error_analysis.ipynb](../notebooks/07_error_analysis.ipynb): o sistema escolhido põe os produtos mais populares no topo? Só no validation set, depois do test set; descritiva, não muda a seleção. A síntese passou a ser a Etapa 7. Funções `error_analysis.product_popularity`, `popularity_profile` e `popularity_by_band`, com testes (275 passando). Notebook reexecutado do início ao fim.
- **Motivo:** a ablation do notebook 04 mostra que o NDCG@10 não muda sem as features de rating, mas não diz se o reranker favorece produtos populares; ele poderia fazer isso sem mudar o NDCG@10.
- **Como:** popularidade = log(1 + `rating_count`), 0 sem rating. Por query, nas ordens da hybrid search e do sistema escolhido (os mesmos 100 candidates): mediana no top 10 e nos candidates, fração sem rating e Spearman correlation entre posição e popularidade; bootstrap de 2.000 reamostragens das queries, seed 0.
- **Resultado:**
  - o top 10 tem um pouco menos ratings que os candidates: −0,404 [−0,644; −0,170] no sistema escolhido e −0,323 [−0,578; −0,069] na hybrid search;
  - o reranker não muda a popularidade do top 10: −0,082 [−0,250; 0,101];
  - fração sem rating no top 10 de 24,2%, contra 21,2% nos candidates, diferença não distinguível de 0;
  - Spearman correlation entre posição e popularidade perto de 0 (+0,047 [0,011; 0,083]).
- **Etapa 6.3, os erros:** um produto pior não é invertido mais vezes quando é o mais popular: taxa de inversão quando o pior é o mais popular − quando é o menos popular, −0,043 [−0,094; 0,016] no sistema escolhido e −0,025 [−0,072; 0,029] na hybrid search, em 67.762 pares; o reranker não muda isso (−0,018 [−0,052; 0,016]). Na mesma query, os Exact sem rating não ficam mais para baixo (+1,1 [−2,8; 5,3] posições, 50 queries). Comparamos taxas, e não contagens de inversões, porque os Irrelevant já têm mais ratings que os Exact entre os candidates. Funções `judged_pair_inversions`, `inversion_counts`, `exact_positions_by_rating` e `bootstrap_pooled`, com testes (280 passando).
- **Registro:** status da proposta de ratings atualizado no [EVALUATION.md](EVALUATION.md); a pergunta original da proposta fica respondida no validation set.

### 2026-11-10: Uma única versão do notebook 01
- **O que foi feito:** removido o `notebooks/01_eda.ipynb` original, e a cópia revisada `01_eda_revised.ipynb` passou a se chamar [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb). As duas traziam os mesmos resultados; a revisada tem o texto reescrito (entrada "Revisão de legibilidade da EDA", 2026-11-08). As entradas anteriores deste DEVLOG que citam `01_eda_revised.ipynb` se referem ao notebook que agora é o `01_eda.ipynb`, e as que citam `01_eda.ipynb` antes de 2026-11-08 se referem à versão original, que fica no histórico do git.
- **Referências atualizadas:** README (tabela de execução, reexecução conferida e estrutura), CONTRIBUTING (modelo de formato) e o markdown dos notebooks 02 revisado, 03 e 04, sem reexecução.
- **Limpeza:** `profiling.py` deixou de reexportar `bootstrap_mean_ci`, que só existia para o notebook original; o teste passou a usar `metrics.bootstrap_mean_ci`.
- O `02_bm25.ipynb` e o `02_bm25_revised.ipynb` continuam como estão.

### 2026-11-10: TL;DR dos notebooks 02 revisado, 03, 04, 06 e 07
- **O que foi feito:** os TL;DR de `notebooks/02_bm25_revised.ipynb`, `03_semantic_hybrid.ipynb`, `04_reranker.ipynb`, `06_test_set.ipynb` e `07_error_analysis.ipynb` foram reescritos para leitores não técnicos, no formato do TL;DR do `01_eda.ipynb`. Só markdown; nenhum notebook foi reexecutado, e cada número foi conferido com as saídas salvas.
- **Formato:** "O que fizemos", "Como medimos" (`label`, NDCG@10 e as outras métricas citadas, e o que quer dizer "não distinguível de 0"), "Principais descobertas", e, quando há, "O que decidimos", "Custo" e "Próximo passo". Os intervalos entre colchetes saíram do TL;DR: cada comparação diz os dois valores e se a diferença é estatisticamente significativa ou não distinguível de 0, como na nota técnica. Os intervalos continuam nas etapas.
- **Correções de conteúdo:**
  - 02: o TL;DR dizia que um quarto dos 10 primeiros não tem `label` sem dizer o set (é o validation set); entraram a composição de `product_features` (`yes`/`no` e números soltos), as piores queries com nota 0 por falta de `label`, o validation set mais difícil que o train set, as entradas inválidas e o custo.
  - 03: entrou que a regra original pela cobertura teria escolhido a BM25 v2 e foi substituída depois de ver o validation set; entraram o overlap das duas listas (47 de 100 no train set) e o resultado de `minnestrista` na semantic search.
  - 04: "sozinho, o cross-encoder ordena pior que o reranker" só vale para a hybrid search, e saiu; o LambdaMART contra o pointwise passa a dizer que a vantagem é na hybrid search; entraram o MRR@10 sem mudança, a escolha `zero` × `drop` como causa do ganho e a latência da busca completa do sistema escolhido.
  - 06: entraram a comparação com o BM25 baseline (0,717 → 0,824) e o MRR@10 (a hybrid search sozinha tem a maior média, e nenhuma diferença do escolhido é distinguível de 0).
  - 07: entraram o aviso de que as categorias de erro e os typos vêm de uma única leitura do assistente de IA, o resto da divisão da perda por categoria e os próximos passos.
- O test set não foi usado de novo.

### 2026-11-10: Notebook 02 revisado: Capped Recall@100 como métrica principal e "catálogo"
- **O que foi feito:** no markdown de `notebooks/02_bm25_revised.ipynb`, o Capped Recall@100 (só Exact) passa a ser apresentado como a métrica principal do notebook, com o NDCG@10 como desempate, que é a regra de tuning já usada na Etapa 4.2. Mudaram o TL;DR, a tabela de métricas e os resultados das Etapas 3.1, 4.3, 4 (resumo) e 5.2. A regra de escolha e os parâmetros escolhidos não mudam.
- **`capped_recall@100_exact_partial`:** já aparecia na tabela do baseline (Etapa 3.1), mas faltava em `METRICS`, então não entrava nas comparações v2 × baseline e v3 × v2. Agora entra, e o markdown cita os valores. Novo resultado no validation set: a v2 sobe de 0,637 para 0,661 (+0,024 [0,002; 0,043]), com intervalo acima de 0; a v3 não se distingue da v2 (−0,003 [−0,007; 0,003]).
- **Correção:** o TL;DR dizia que o validation set é "mais difícil" para o BM25, mas isso só vale para as métricas de ordem; o Capped Recall@100 do baseline é 0,702 no validation set e 0,697 no train set.
- **Termo:** "catalog" virou "catálogo" no markdown do notebook 02.
- Notebook reexecutado do início ao fim; os números deterministas não mudaram, e os tempos (indexação, latência, tuning) foram atualizados para a nova execução salva. O test set não foi usado.

### 2026-11-10: TL;DR do notebook 02 revisado em registro mais formal
- **O que foi feito:** o TL;DR de `notebooks/02_bm25_revised.ipynb` foi reescrito num registro mais formal e preciso. A versão anterior, escrita para leitores não técnicos, ficou informal demais ("não ajuda a busca", "não melhora nada", "nota 0 nem sempre quer dizer resultado ruim"). A estrutura, os números e as etapas citadas não mudam.
- **Correção de conteúdo:** a alta do `capped_recall@100_exact_partial` da v2 (0,637 → 0,661) passa a dizer que a diferença é significativa, como mostra a Etapa 4.3; "cobertura" foi trocada por Capped Recall@100, o termo do notebook.
- Só markdown; nenhum notebook foi reexecutado. O test set não foi usado.
- **Tabela e valores finais:** o TL;DR ganhou a tabela "Resultados no validation set" com as seis métricas de baseline, v2 e v3 e a significância das comparações v2 × baseline e v3 × v2, e as definições de MRR@10, judged@10 e condensed NDCG@10. O item sobre produtos sem `label` dizia que o NDCG@10 "subiria 0,16" sem dizer a versão (era o baseline); agora traz os valores finais do baseline (0,620 → 0,781) e da v2 (0,653 → 0,799).
- **Intervalos na tabela:** na tabela do TL;DR, as colunas de comparação trazem a diferença média e o CI 95% do paired bootstrap, em vez de "significativa"; o texto do TL;DR continua sem intervalos.
- **Latência:** entrou no TL;DR um item sobre a latência do BM25 (p50 de 0,8 ms e p95 de 3,0 ms na execução salva; v2 na mesma ordem de grandeza do baseline; uma única máquina, sem valor de estimativa de produção), com os números das Etapas 2.4 e 4.3.
- **Foco no Capped Recall@100:** as "Principais descobertas" do TL;DR do 02 foram reorganizadas em torno da métrica principal: cerca de 70% dos Exact entre os 100 candidatos em todas as versões (com o ganho da v2 no train set que não se confirma no validation set), o Capped Recall com 50, 100 e 200 candidatos e o `capped_recall@100_exact_partial`. O NDCG@10 aparece só como desempate e no item sobre produtos sem `label`, que juntou o item das queries com NDCG@10 = 0 e passou a dizer que esses produtos afetam o NDCG@10, mas não o Capped Recall@100. O item de latência ganhou o tempo de construção do índice.
- **Limitações:** o TL;DR do 02 ganhou a seção "Limitações": typos não corrigidos; keys de `product_features` concatenadas e não separadas (efeito não avaliado); as três mudanças da v2 aplicadas juntas, sem ablation.

### 2026-11-10: Uma única versão do notebook 02
- **O que foi feito:** removido o `notebooks/02_bm25.ipynb` original, e a cópia revisada `02_bm25_revised.ipynb` passou a se chamar [notebooks/02_bm25.ipynb](../notebooks/02_bm25.ipynb), como já tinha sido feito com o notebook 01. As entradas anteriores deste DEVLOG que citam `02_bm25_revised.ipynb` se referem ao notebook que agora é o `02_bm25.ipynb`, e as que citam `02_bm25.ipynb` antes de 2026-11-08 se referem à versão original, que fica no histórico do git. As referências do `docs/EVALUATION.md` ao `02_bm25.ipynb` continuam válidas: as etapas citadas têm a mesma numeração e os mesmos resultados.
- **Referências atualizadas:** README (tabela de execução, latência e custo, e estrutura, que deixa de citar a versão original), CONTRIBUTING (modelo de formato), o markdown dos notebooks 03, 04 e 05 e a docstring de `wands_search.systems`, sem reexecução.

### 2026-11-10: TL;DR do notebook 03 no formato do 02
- **O que foi feito:** o TL;DR de `notebooks/03_semantic_hybrid.ipynb` foi reescrito no mesmo registro e formato do `02_bm25.ipynb`: Capped Recall@100 como métrica principal e NDCG@10 como desempate (a regra de tuning das Etapas 3.1, 5.2 e 5.3); a palavra "cobertura" saiu, e a métrica é sempre nomeada.
- **Tabela:** "Resultados no validation set" com Capped Recall@100, @50 e @200, `capped_recall@100_exact_partial`, NDCG@10, MRR@10, judged@10 e condensed NDCG@10 dos três sistemas, e as diferenças pareadas com CI 95%.
- **Itens novos, da revisão do notebook inteiro:** Capped Recall@50 e @200 da hybrid search contra a semantic search; o teto da união das duas listas (0,818 e 0,892) e quanto a hybrid search aproveita dele (Etapas 5.1 e 5.2); a vantagem de Capped Recall@100 do train set (0,754 contra 0,731) que não se confirma no validation set; queries com cor ou acabamento (Etapa 7.4); latência dos três sistemas, com p50 e p95 e a variação entre execuções; custo dos embeddings; seção "Limitações" (um único embedding model, intervalos largos com 77 queries, regra substituída depois do validation set, corte em 512 wordpieces, análises por tipo de query descritivas, latência de uma máquina).
- Só markdown; nenhum notebook foi reexecutado. O test set não foi usado.
- **Embedding model:** a limitação "um único embedding model" do TL;DR do 03 passou a dizer o motivo (tempo de gerar os embeddings do catalog a cada modelo; `torch` para o fine-tuning). O `docs/EVALUATION.md` ganhou o item 8 dos "Trabalhos futuros": testar outros modelos pré-treinados que o `fastembed` já roda sem `torch` (`all-MiniLM-L6-v2`, `bge-base-en-v1.5`), com custo, latência, memória e o fato de o test set já ter sido rodado.
- **Pooling bias no Capped Recall@100:** nova limitação no TL;DR do 03: a métrica principal pode favorecer a BM25 v2, porque o pool do WANDS incluiu uma lexical search e a semantic search tem judged@100 menor (0,627 contra 0,676); o tamanho do efeito não foi medido. Usa o token overlap da Etapa 5.1 do `01_eda.ipynb` (48,5% contra 1,8%), e não os 83% dos produtos com todos os tokens, que são só 4,5% dos produtos julgados (conta feita fora do notebook, não citada).

