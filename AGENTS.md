# Regras operacionais do repositório

## Publicação obrigatória de commits

Todo commit local criado neste repositório deve ser publicado remotamente na
mesma execução de trabalho.

1. Antes do commit, revisar os arquivos staged e executar as validações
   pertinentes ao escopo alterado.
2. Criar o commit somente com arquivos revisados; nunca incluir por acidente
   bancos SQLite, APKs, `.env`, credenciais, dados pessoais, caches, artefatos
   de build ou arquivos internos em `.hermes/`.
3. Imediatamente após um commit bem-sucedido, executar:

   ```bash
   branch=$(git branch --show-current)
   git push origin "$branch"
   ```

4. A publicação só é considerada concluída após comparar o SHA local com a
   referência concreta remota, nunca apenas com a saída do `git push`:

   ```bash
   branch=$(git branch --show-current)
   local_sha=$(git rev-parse HEAD)
   remote_sha=$(git ls-remote origin "refs/heads/$branch" | cut -f1)
   test -n "$remote_sha" && test "$local_sha" = "$remote_sha"
   ```

5. Se o push ou a confirmação do SHA falhar, informar o bloqueio de forma
   explícita e não declarar o commit como entregue. Não usar `--force`,
   `--force-with-lease`, rebase destrutivo ou alteração de histórico sem
   autorização explícita do proprietário.

Esta regra não dispensa a revisão do escopo nem autoriza a publicação de
alterações de terceiros ou arquivos não revisados.
