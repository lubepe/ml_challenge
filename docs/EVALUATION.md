# Protocolo de avaliação

Este documento registra o protocolo e todas as suas versões. Cada mudança entra como nova versão, com data e motivo, sem sobrescrever a anterior. Itens marcados como **A definir** ainda não foram decididos. A versão 0 é um rascunho e é editada diretamente; o versionamento começa na versão 1, quando o protocolo fechar.

## Regras fixas (do enunciado)

- O dataset não tem split oficial, então definimos e justificamos o nosso.
- O sistema é selecionado na validação.
- O teste é reportado uma única vez.

## Versão 0 (rascunho, 2026-11-05)

### Split
- **A definir:** proporções e seed.
- **Regra:** cada query fica inteira em uma única parte, qualquer que seja o número de produtos julgados, para simular buscas que o sistema nunca viu.
- **Decidido:** divisão por query, com seed fixa, estratificada por duas informações combinadas, em 12 grupos (o menor tem 18 queries):
  - fração de `label` = Exact da query, em 4 faixas (nenhum: 101 queries; até 2%: 106; de 2% a 10%: 88; acima de 10%: 185);
  - número de produtos julgados da query, em 3 faixas de tamanho parecido (de 1 a 149; de 150 a 340; de 344 a 4.329).
- **Motivo:** as queries variam muito nas duas informações, e 10% das queries concentram 47% dos pares. Em 200 sorteios com proporção ilustrativa de 70/15/15, a parte de teste ficou com de 11,8% a 17,1% dos pares (percentis 5 e 95) usando as duas informações, contra de 10,8% a 18,5% usando só a fração de Exact. Fonte: `notebooks/01_eda.ipynb`, Etapa 4.
- **Depois da divisão:** conferimos se as partes ficaram parecidas em tamanho de `query`, em número de pares e em distribuição de `label`. A seed não pode ser escolhida olhando resultados de modelos.
- **Não usar `query_class` para estratificar:** 139 dos 188 valores têm menos de 3 queries.
- **Proposta:** "leather chair" e "leather chairs", as únicas queries quase iguais encontradas, ficam na mesma parte da divisão. `split.stratified_split` ainda não faz isso.
- **A definir:** arquivo com os `query_id` de cada split, versionado em `splits/`.

### O que conta como relevante
- **A definir:** mapeamento dos rótulos em ganhos. Proposta inicial: Exact = 2, Partial = 1, Irrelevant = 0.
- **A definir:** limiar binário para métricas de retrieval, por exemplo Exact e Partial como relevantes.
- **Proposta (a confirmar com o primeiro BM25):** produto retornado sem rótulo para a query conta como irrelevante na nota principal, por ser a opção conservadora. Junto com ela, reportamos a porcentagem de resultados com rótulo entre os K primeiros. Se essa porcentagem for baixa para algum sistema, calculamos também a nota ignorando os produtos sem rótulo, para ver se a conclusão muda. Motivo: cada query tem na mediana 215 produtos julgados (0,50% do catálogo), e os julgados não são aleatórios: têm 48,5% das palavras da query, contra 1,8% de produtos aleatórios. Dos produtos com todas as palavras da query em `product_name`, `product_class` ou `category_hierarchy`, 83% foram julgados. O risco maior é para sistemas semânticos, que podem retornar produtos relevantes sem as palavras da query e sem rótulo. Fonte: `notebooks/01_eda.ipynb`, Etapa 5.
- **Proposta:** deduplicação de `label.csv`. Removemos as 1.561 linhas que são cópias exatas (ignorando o `id`). Excluímos os 14 pares (query, produto) com rótulos diferentes, porque não temos regra de negócio para escolher um deles; esses pares passam a ser tratados como produtos sem rótulo para a query. Restam 231.859 pares. Implementada em `data.deduplicate_labels`. Fonte: `notebooks/01_eda.ipynb`, Etapas 1 e 4.

### Métricas
- **Proposta:** a nota final é a média por query, então cada query pesa o mesmo, tenha ela 1 ou 4.329 produtos julgados.
- **Proposta:** queries sem nenhum produto relevante saem das métricas que exigem um produto relevante, mas ficam na divisão. Hoje é só "drudge report" (considerando Exact e Partial como relevantes). Se só Exact contasse, seriam 101 queries.
- **Retrieval (A definir):** Recall@K e MRR, com K a escolher.
- **Ranking (A definir):** NDCG@K com ganho graduado, e talvez MAP.

### Entradas permitidas
- **Decidido:** a entrada do sistema é só o texto da busca, sem filtro escolhido pelo usuário, porque o dataset não registra filtros.
- **Decidido:** `query_class` não entra como entrada direta de nenhum sistema, porque uma busca real não traz essa informação (vazamento de dados). Só uma previsão feita a partir do texto da busca poderia ser usada.
- **Decidido:** `product_id` não entra como feature do modelo de ranking, para que ele não decore produtos e funcione com produtos que não viu no treino.
- **A medir depois da divisão:** quantos produtos de validação e teste não aparecem no treino.
- **Decidido:** sem filtro automático por categoria. Um erro removeria os produtos certos antes do ranking, e 1.556 produtos não têm `category_hierarchy`.

### Comparação entre sistemas
- **A definir:** mesmas queries e mesmo conjunto de candidatos para todos os sistemas.
- **A definir:** intervalo de confiança por bootstrap sobre queries e teste de significância.

### Seleção e teste
- **A definir:** critério de seleção na validação.
- **A definir:** registrar aqui a data em que o teste foi rodado, para garantir uma única vez.

## Histórico de resultados

Tabela a preencher, uma linha por sistema e por split.

| Data | Sistema | Split | Recall@K | MRR | NDCG@K | Observações |
|---|---|---|---|---|---|---|
| | | | | | | |
