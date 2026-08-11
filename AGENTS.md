# Regras operacionais do repositório

## Gestão de commits locais

Os commits locais criados neste repositório não devem ser enviados automaticamente para o servidor remoto (`git push`).

1. Antes do commit, revisar os arquivos staged e executar as validações
   pertinentes ao escopo alterado.
2. Criar o commit somente com arquivos revisados; nunca incluir por acidente
   bancos SQLite, APKs, `.env`, credenciais, dados pessoais, caches, artefatos
   de build ou arquivos internos em `.hermes/`.
3. Manter os commits apenas no repositório local. O envio para o repositório
   remoto (`git push`) só deve ser executado mediante solicitação ou autorização
   explícita do proprietário.
4. Quando o push remoto for autorizado e executado, confirmar a publicação
   comparando o SHA local com a referência concreta remota:

   ```bash
   branch=$(git branch --show-current)
   local_sha=$(git rev-parse HEAD)
   remote_sha=$(git ls-remote origin "refs/heads/$branch" | cut -f1)
   test -n "$remote_sha" && test "$local_sha" = "$remote_sha"
   ```

5. Não usar `--force`, `--force-with-lease`, rebase destrutivo ou alteração de
   histórico sem autorização explícita do proprietário.

Esta regra não dispensa a revisão do escopo nem autoriza a publicação de
alterações de terceiros ou arquivos não revisados.

