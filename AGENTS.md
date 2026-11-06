# Instruções para agentes

Sistema de busca e ranking de produtos sobre o dataset WANDS. Visão geral em [README.md](README.md).

Antes de trabalhar, leia e siga todas as convenções de [CONTRIBUTING.md](CONTRIBUTING.md).

## Regras específicas para agentes

- Ao concluir uma etapa, adicione uma entrada em `docs/DEVLOG.md`. Decisões que afetam a avaliação também vão para `docs/EVALUATION.md`.
- Nunca rode avaliação no conjunto de teste sem pedido explícito. O teste é rodado uma única vez.
- Trabalhe em etapas pequenas e mostre os resultados antes de seguir para a próxima.
- Se existir um `HANDOVER.md` local, leia-o no início da sessão para recuperar o estado do trabalho.
- Antes de propor ou criar um commit, siga o checklist "Antes de cada commit" do `CONTRIBUTING.md`, incluindo a atualização do README.

## Comandos

- Instalar: `uv sync`
- Testes: `uv run pytest`
- Executar um notebook: `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/<nome>.ipynb`
