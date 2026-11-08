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

- Feitos em etapas. Antes de cada etapa ou análise, uma célula markdown explica o que estamos explorando.
- As conclusões ficam logo abaixo da célula de código que as sustenta, sempre que possível, e não só no fim da etapa.
- O markdown dos notebooks pode ser em português; o código segue a regra de idioma acima.
- Conclusões só afirmam o que as saídas mostram.
- **Suposições explícitas:** toda suposição feita em uma análise é declarada no notebook, junto da conclusão que depende dela.
- **Alternativas explícitas:** toda escolha, mesmo proposta ou provisória, vem acompanhada das outras opções possíveis.
- **Fontes externas:** o que vier de fora do dataset, como artigos e documentação, cita o link da fonte e fica separado do que os nossos dados mostram.

## Gráficos

- Feitos com seaborn, usando o estilo de `wands_search.plots`.
- Vários painéis ficam em uma coluna e múltiplas linhas, nunca lado a lado.
- Cada gráfico se explica sozinho, porque pode ser lido fora do notebook. O título diz o que é medido e em quais dados; os eixos usam nomes explícitos; termos técnicos são definidos numa nota abaixo do gráfico.
- Todo gráfico que fala em token traz uma nota explicando como o token é calculado (`plots.TOKEN_DEFINITION`).
- O texto dos gráficos fica em inglês, como o resto do código.

## Terminologia

- Ao falar de uma coluna, use sempre o nome dela (`category_hierarchy`, `product_class`, `product_description`), em texto e em código. Nada de sinônimos ou traduções, como "hierarquia", "caminho", "path" ou "classe".
- O mesmo vale para qualquer conceito do projeto: escolha um termo e use só ele.

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
