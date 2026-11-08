# Protocolo de avaliação

Este documento registra o protocolo e todas as suas versões. Cada mudança entra como nova versão, com data e motivo, sem sobrescrever a anterior. Itens marcados como **A definir** ainda não foram decididos. A versão 0 é um rascunho e é editada diretamente; o versionamento começa na versão 1, quando o protocolo fechar.

## Regras fixas (do enunciado)

- O dataset não tem split oficial, então definimos e justificamos o nosso.
- O sistema é selecionado na validação.
- O teste é reportado uma única vez.

## Versão 0 (rascunho, 2026-11-05)

### Split
- **Decidido (2026-11-08):** proporção 60/20/20 (treino, validação, teste), cerca de 287, 96 e 96 queries com as 479 restantes. Motivo: com 15%, o teste teria cerca de 70 queries e métricas muito ruidosas. **Alternativa:** 70/15/15, que dá mais dados ao treino do ranking. **Decidido (2026-11-08):** `seed = 87`, escolhida antes de ver qualquer resultado de modelo e que não muda depois.
- **Regra:** cada query fica inteira em uma única parte, qualquer que seja o número de produtos julgados, para simular buscas que o sistema nunca viu. Nenhum `query_id` aparece em duas partes. Um teste em `tests/test_split.py` confere que as partes são disjuntas e cobrem todas as queries.
- **Decidido e implementado (2026-11-08):** excluir, antes da divisão, as queries sem nenhum produto com `label` Exact ou Partial. Hoje é só `query_id` 366 ("drudge report"), com um único par, Irrelevant. Restam 479 queries. Motivo: sem produto relevante, Recall@K, MRR e NDCG@K não existem ou valem 0 para qualquer sistema, e um par Irrelevant não ensina nada ao ranking. **Alternativa:** manter a query e tirá-la só das métricas, que deixaria o conjunto de queries com duas definições. A regra é geral, não escrita para um `query_id`. As queries com um único relevante (`query_id` 179 e 462) ficam, e a nota delas é muito ruidosa.
- **Decidido e implementado (2026-11-08):** "leather chair" e "leather chairs", as únicas queries quase iguais encontradas por `profiling.query_group_key`, ficam na mesma parte: o sorteio trata cada grupo de queries quase iguais como um bloco. Implementado em `split.split_queries`: o bloco vai para a parte do sorteio do seu menor `query_id`, e conta como uma query no sorteio.
- **Substituído por `exact_share` (versão anterior):** divisão por query, com seed fixa, estratificada por duas informações combinadas, em 12 grupos (o menor tem 18 queries):
  - fração de `label` = Exact entre os produtos julgados da query (`exact_fraction`), em 4 faixas (nenhum: 101 queries; até 2%: 106; de 2% a 10%: 88; acima de 10%: 185);
  - número de produtos julgados da query (`n_judged`), em 3 faixas de tamanho parecido (de 1 a 149; de 150 a 340; de 344 a 4.329).
- **Decidido e implementado (2026-11-08):** trocar `exact_fraction` por `Exact / (Exact + Partial)`, sem Irrelevant no denominador. Motivo: o número de Irrelevant depende de quantos candidatos entraram para julgamento, não só da query, então ele mistura a proporção de Exact com a profundidade do conjunto julgado. Medido nos dados: a ordem das queries quase não muda (correlação de postos 0,975 entre `exact_share` e `Exact / n_judged`, Etapa 4.6), então o impacto esperado é pequeno. Os cortes passam a ser 0, 5% e 25% (mediana da nova medida 0,065 contra 0,043 da anterior), que dão grupos de 100, 125, 110 e 144 queries. Não fazemos simulação de seeds: com a seed fixa a divisão é determinística, e a checagem é feita no split final (queries por parte, tamanho do menor grupo, distribuição de `n_judged` e da fração de Exact em cada parte). A decisão anterior (cortes de 2% e 10% sobre `exact_fraction`) fica substituída. `n_judged` continua como segunda dimensão, pelo motivo descrito abaixo. Ele também inclui Irrelevant; a alternativa é usar `Exact + Partial` no lugar, mas não vemos ganho claro.
- **Suposição:** uma parte com mais queries de `exact_share` alto teria notas maiores só por isso, e a composição dos `label` se relaciona com a dificuldade da query para um buscador. Não medimos nenhuma das duas coisas. Podem ser medidas depois com o primeiro BM25, só em treino e validação. A composição também pode refletir o pooling. `n_judged` não indica composição nem dificuldade: a correlação de postos com `exact_share` é −0,013 (Etapa 4.6).
- **Decidido e implementado:** distribuir o resto do arredondamento entre as partes, em vez de dar tudo à última (o que deixava a última parte abaixo da proporção pedida).
- **Variáveis de estratificação (definições):** ambas são numéricas e viram faixas (categorias) só para formar os grupos.
  - `exact_share` = `Exact / (Exact + Partial)`: contínua, de 0 a 1. Mede, entre os produtos relevantes da query, a fração que é Exact. Não mede dificuldade. Faixas: 0; até 5%; de 5% a 25%; acima de 25%.
  - `n_judged`: contagem de produtos com `label` para a query (de 1 a 4.329), incluindo Irrelevant. Mede o tamanho do conjunto julgado, não a dificuldade. Faixas: 3, com quantidade parecida de queries (de 1 a 149; de 150 a 340; de 344 a 4.329).
  - **Alternativas:** `Exact / n_judged` (Irrelevant no denominador); `Exact + Partial` no lugar de `n_judged`; não cortar em faixas e distribuir as queries ordenadas pelo valor.
- **Motivo da estratificação:** as métricas são médias por query, então importa que as partes tenham distribuições parecidas das duas informações, e não o número de pares de cada parte. Com ganho graduado (Exact = 2, Partial = 1), uma query com muitos Exact permite pontuar alto mais facilmente do que uma com quase só Partial, em que um único Exact decide a nota. Se uma parte tiver por acaso muito mais queries do primeiro tipo, o sistema pontuaria mais nela sem ser melhor, e a estratificação por `exact_share` mantém a mesma mistura nas três partes. `n_judged` se relaciona com quantos relevantes a query tem (correlação de postos 0,880 com `Exact + Partial`, contra 0,516 com `Irrelevant`; Etapa 4.6), o que afeta métricas como Recall@K. A simulação de 200 seeds que existia numa versão anterior da Etapa 4.6 do notebook media a fração de pares do teste, que não é o critério da avaliação, e não sustenta esta decisão. Ela foi removida do notebook. Fonte: `notebooks/01_eda.ipynb`, Etapa 4.
- **Não estratificar pela fração de Irrelevant:** só 8 das 479 queries têm 90% ou mais de Irrelevant (Etapa 4.6), e uma terceira dimensão criaria grupos pequenos demais. A distribuição da fração de Irrelevant é conferida depois da divisão.
- **Não usar `query_class` para estratificar:** 139 dos 188 valores têm menos de 3 queries, e a informação não existe em produção. Usar `query_class` para escolher a parte da query não vaza dados, porque o sistema não recebe o split. `query_class` fica para a análise de erros, agrupando os valores mais comuns.
- **Depois da divisão:** conferimos se as partes ficaram parecidas em tamanho de `query`, em número de pares, em distribuição de `label` e em fração de Irrelevant por query.
- **Produtos compartilhados entre partes:** é esperado. No split final, 94,7% dos pares da validação e 92,7% dos do teste têm um `product_id` que também foi julgado no treino, porque o catálogo é o mesmo (Etapa 4.6). Isso não é vazamento de query. Só seria problema se `product_id` fosse feature do ranking, o que não é permitido (ver Entradas permitidas).
- **Decidido e implementado:** os `query_id` de cada parte ficam em `splits/query_split.csv`, versionado, gerado por `uv run python -m wands_search.split`. Resultado com `seed = 87`: 287 queries em treino, 97 em validação e 95 em teste (o bloco "leather chair" tem duas queries). O menor grupo de estratificação tem 25 queries.
- **Alternativa se o ruído do teste atrapalhar a seleção:** validação cruzada por query sobre treino e validação juntos, mantendo o teste separado e rodado uma única vez.

### O que conta como relevante
- **Decidido (2026-11-08):** ganho graduado: Exact = 2, Partial = 1, Irrelevant = 0.
- **Decidido (2026-11-08):** nas métricas que separam relevante de não relevante (Capped Recall@100 e MRR@10), relevante = só Exact. A definição ampla (Exact e Partial) é só secundária. Detalhes na seção Métricas.
- **Decidido (2026-11-08):** produto retornado sem rótulo para a query tem ganho 0 na nota principal (NDCG@10), por ser a opção conservadora. Junto com ela, reportamos judged@10 (porcentagem de resultados com rótulo entre os 10 primeiros) e o NDCG@10 só com produtos julgados, para ver se a conclusão muda. Motivo: cada query tem na mediana 215 produtos julgados (0,50% do catálogo), e os julgados não são aleatórios: têm 48,5% das palavras da query, contra 1,8% de produtos aleatórios. Dos produtos com todas as palavras da query em `product_name`, `product_class` ou `category_hierarchy`, 83% foram julgados. O risco maior é para sistemas semânticos, que podem retornar produtos relevantes sem as palavras da query e sem rótulo. Fonte: `notebooks/01_eda.ipynb`, Etapa 5.
- **Proposta:** deduplicação de `label.csv`. Removemos as 1.561 linhas que são cópias exatas (ignorando o `id`). Excluímos os 14 pares (query, produto) com rótulos diferentes, porque não temos regra de negócio para escolher um deles; esses pares passam a ser tratados como produtos sem rótulo para a query. Restam 231.859 pares. Implementada em `data.deduplicate_labels`. Fonte: `notebooks/01_eda.ipynb`, Etapas 1 e 4.

- **Suposição:** ao que tudo indica, um `product_id` pode incluir vários SKUs (versões vendáveis de um produto, como a mesma cama nos tamanhos queen e king): 66,3% dos produtos com `mattresssize` têm mais de um valor. O dataset não documenta isso. **Proposta:** `product_id` é a unidade da busca e da avaliação, porque `label` é dado nesse nível e não indica qual SKU foi julgado. Fonte: `notebooks/01_eda.ipynb`, Etapa 2.5.

### Métricas
- **Proposta:** a nota final é a média por query, então cada query pesa o mesmo, tenha ela 1 ou 4.329 produtos julgados.
- **Decidido:** o NDCG@10 cobre as 479 queries. Capped Recall@100 e MRR@10 usam só as 379 que têm Exact, e o n de cada split é informado junto com a métrica.
- **Decidido (2026-11-08), métrica principal (seleção do sistema):** NDCG@10, com ganhos Exact = 2, Partial = 1 e Irrelevant = 0. Cobre as 479 queries, porque nenhuma fica sem produto Exact ou Partial. Produto sem `label` conta como ganho 0.
- **Decidido (2026-11-08), retrieval:** Capped Recall@100 = produtos Exact encontrados nos 100 primeiros ÷ min(100, número de Exact da query). Relevante = só Exact. Exclui as 100 queries sem Exact, restando **n = 379** (treino 227, validação 77, teste 75). Esse n é informado por split junto com a métrica. Reportamos também Capped Recall@50 e @200, junto com a latência do reranker, para justificar K = 100.
- **Decidido (2026-11-08), ranking:** MRR@10 com relevante = só Exact, nas mesmas 379 queries.
- **Decidido (2026-11-08), secundárias e diagnóstico:** Capped Recall@100 com Exact e Partial (definição ampla, opcional); judged@10; e NDCG@10 só com produtos julgados, para checar o efeito dos produtos sem `label`.
- **Correção de número:** a especificação original citava 101 queries sem Exact e n = 378. Essas 101 são da base de 480 e incluem a query 366 ("drudge report"), que já é excluída antes da divisão. Na base de 479, são 100 sem Exact e n = 379.
- **Todas as métricas são calculadas, por query e depois em média, sobre a ordem de todas as etapas**, para a comparação ser consistente:

  | Sistema | NDCG@10 | MRR@10 (Exact) | Capped Recall@100 (Exact) | judged@10 |
  |---|---|---|---|---|
  | BM25 (baseline) | sim | sim | sim | sim |
  | Vetorial | sim | sim | sim | sim |
  | Híbrido (RRF) | sim | sim | sim | sim |
  | Híbrido + reranker | sim | sim | = híbrido | sim |

  - **Retrieval e ranking:** os dois nomes só indicam o que cada métrica avalia melhor, não onde ela é calculada. Capped Recall@100 avalia melhor o retrieval (cobertura); NDCG@10 e MRR@10 avaliam melhor a ordem, ou seja, o ranking.
  - **Única exceção:** o Capped Recall@100 do reranker. Ele só reordena os mesmos 100 candidatos do híbrido, então o valor é idêntico ao do híbrido por construção.
  - **Baseline do ranking:** NDCG@10 e MRR@10 nas linhas sem reranker são o ponto de partida. A diferença entre "Híbrido (RRF)" e "Híbrido + reranker" mede quanto o ranking ajuda.
  - **NDCG@10 é a métrica principal**, com o MRR@10 ao lado. Na nota técnica, o MRR é chamado de métrica de ranking, aplicada à saída do retrieval como baseline: ele mede a ordem, e o trabalho do retrieval em si é cobertura.
  - **K = 100** candidatos passam do retrieval para o ranking.
  - **Latência** (p50 e p95, em ms) entra na tabela de resultados, medida separadamente para retrieval e ranking. No reranker, a latência do retrieval é a do híbrido, e a do ranking é a do reranker.
- **Definições** (cada métrica é calculada por query):
  - **NDCG@10:** qualidade da ordem nos 10 primeiros resultados, com ganho graduado (Exact = 2, Partial = 1, Irrelevant = 0; produto sem `label` = 0). O ganho de cada posição é descontado conforme ela desce na lista, e a soma é dividida pela soma da melhor ordem possível para a query, então vai de 0 a 1.
  - **MRR@10:** 1 dividido pela posição do primeiro produto Exact nos 10 primeiros resultados (0 se não houver). A média sobre as queries é o MRR.
  - **Capped Recall@100:** número de produtos Exact nos 100 primeiros resultados, dividido pelo menor valor entre 100 e o número de Exact da query. Vai de 0 a 1, e 1 significa que nenhum sistema poderia fazer melhor. O teto só muda a conta em 74 das 379 queries (as que têm mais de 100 Exact); sem o teto, o valor máximo teria média de 0,92.
  - **judged@10:** fração dos 10 primeiros resultados que têm algum `label` para a query (Exact, Partial ou Irrelevant). Não mede qualidade: mostra quanto da nota se apoia em produtos rotulados.
  - **NDCG@10 só com produtos julgados:** é o NDCG@10 calculado depois de remover da lista os produtos sem `label`, para ver quanto a nota depende do ganho 0 dado a eles. (Leitura nossa da especificação; a implementação precisa seguir exatamente isto.)
  - **RRF (Reciprocal Rank Fusion):** junta duas listas ordenadas dando a cada produto a soma de 1 / (constante + posição) em cada lista; a ordem final é pela soma. É o que forma a ordem do "Híbrido (RRF)".
- **Alternativas consideradas:** relevante = Exact e Partial no Capped Recall@100 e no MRR@10, que manteria todas as 479 queries mas faria o Recall@100 sem teto ter média de 0,59 no melhor caso; fica como secundária, opcional.

### Entradas permitidas
- **Decidido:** a entrada do sistema é só o texto da busca, sem filtro escolhido pelo usuário, porque o dataset não registra filtros.
- **Decidido:** `query_class` não entra como entrada direta de nenhum sistema, porque uma busca real não traz essa informação (vazamento de dados). Só uma previsão feita a partir do texto da busca poderia ser usada.
- **Decidido:** `product_id` não entra como feature do modelo de ranking, para que ele não decore produtos e funcione com produtos que não viu no treino.
- **Medido no split final (Etapa 4.6):** 2.155 dos 25.388 produtos distintos da validação e 2.587 dos 25.112 do teste não têm nenhum par julgado no treino.
- **Decidido:** sem filtro automático por categoria. Um erro removeria os produtos certos antes do ranking, e 1.556 produtos não têm `category_hierarchy`.
- **Proposta:** não usar imputação pela moda (preencher o nulo com o valor mais comum dos produtos do mesmo grupo) em `product_class` e `category_hierarchy` no primeiro sistema. O erro held-out, medido em 20% dos produtos separados do cálculo da moda, é de 5,9% para `product_class` e 24,3% para `category_hierarchy`. Isso daria cerca de 157 e 335 produtos com valores errados, supondo a mesma taxa nos produtos com nulo. Um valor errado pode trazer o produto para a query errada e parece um dado original. Outras opções só são testadas na validação se a análise de erros mostrar produtos relevantes perdidos por causa desses nulos. Fonte: `notebooks/01_eda.ipynb`, Etapa 2.3.
- **Suposição:** os dados representam produção, ou seja, `product_class` e `category_hierarchy` também podem estar nulos em produção. O dataset não confirma isso. Se todo produto tivesse as duas colunas em produção, revemos a proposta acima, para que o modelo não aprenda com nulos que não existirão: imputar os dados de treino e avaliação ou deixar os produtos com nulo fora do treino do ranking. Valores imputados continuariam menos confiáveis do que os reais, principalmente em `category_hierarchy`.
- **Proposta:** usar `product_class` comparando-o com o texto da query, sem depender de `query_class`. Começamos com o texto pesquisável no retrieval e uma feature de semelhança no ranking. Prever o `product_class` da query, por classificação de queries ou *pseudo-relevance feedback*, só é testado na validação se a análise de erros mostrar que a categoria faz falta. Fonte: `notebooks/01_eda.ipynb`, Etapa 4.5.

### Comparação entre sistemas
- **A definir:** mesmas queries e mesmo conjunto de candidatos para todos os sistemas.
- **A definir:** intervalo de confiança por bootstrap sobre queries e teste de significância.
- **Proposta:** a ablação do ranking compara o modelo com e sem `rating_count`, `average_rating` e `review_count`, e a análise de erros confere se os erros se concentram em produtos muito populares ou sem avaliação. Motivo: 22,0% dos produtos não têm avaliação, e os 10% dos produtos avaliados com maior `rating_count` têm 79,5% das avaliações, então essas colunas podem favorecer produtos populares. A nota mede se o produto atende à query, não se ele vende bem; um ganho pequeno aqui não prova que popularidade é inútil em produção. Fonte: `notebooks/01_eda.ipynb`, Etapa 2.1.

### Seleção e teste
- **A definir:** critério de seleção na validação.
- **A definir:** registrar aqui a data em que o teste foi rodado, para garantir uma única vez.

## Histórico de resultados

Tabela a preencher, uma linha por sistema e por split, com o n de queries de cada métrica nas observações (NDCG@10: 479; MRR@10 e Capped Recall@100: 379). Os sistemas são BM25 (baseline), Vetorial, Híbrido (RRF) e Híbrido + reranker. Para o reranker, o Capped Recall@100 é o do híbrido.

| Data | Sistema | Split | NDCG@10 | MRR@10 (Exact) | Capped Recall@100 (Exact) | judged@10 | Latência retrieval p50 / p95 (ms) | Latência ranking p50 / p95 (ms) | Observações |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |
