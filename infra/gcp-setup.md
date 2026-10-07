# Publicação no Google Cloud Run

Passo a passo para colocar o site no ar com domínio próprio. Feito uma vez;
depois disso, todo push na `main` publica sozinho pela esteira
(`.github/workflows/pipeline.yml`).

Custo esperado: R$ 0 de hospedagem (o site cabe no nível gratuito do Cloud
Run) mais o domínio, cerca de R$ 40 por ano.

> Estes comandos não foram executados por quem escreveu o guia: dependem das
> suas contas. Confira cada saída antes de seguir para o próximo passo.

## Antes de começar

1. Conta no Google Cloud com faturamento ativo (pede cartão):
   <https://console.cloud.google.com/billing>
2. `gcloud` instalado: <https://cloud.google.com/sdk/docs/install>
3. Repositório `viniciussilva2/portfolio` criado no GitHub, com este código na
   branch `main`.
4. Para o passo 9, um domínio já registrado.

Os comandos abaixo são para o **Git Bash**. Rode primeiro:

```bash
gcloud auth login

PROJECT_ID="portfolio-vinicius"   # precisa ser único no mundo; troque se já existir
REGION="us-east1"                 # região com domínio próprio gratuito no Cloud Run
REPO="viniciussilva2/portfolio"
```

## 1. Projeto e serviços

```bash
gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Vincular à conta de faturamento (liste com: gcloud billing accounts list)
gcloud billing projects link "$PROJECT_ID" --billing-account="XXXXXX-XXXXXX-XXXXXX"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
```

## 2. Alerta de gasto

No console: **Faturamento → Orçamentos e alertas → Criar orçamento**, valor
R$ 5, alerta em 50% e 100%.

O alerta avisa por e-mail; ele **não bloqueia** a cobrança. O que limita o pior
caso é o `--max-instances 2` da esteira.

## 3. Onde as imagens ficam

```bash
gcloud artifacts repositories create portfolio \
  --repository-format=docker --location="$REGION"

# Mantém só as 3 imagens mais recentes, para ficar dentro do 0,5 GB gratuito.
gcloud artifacts repositories set-cleanup-policies portfolio \
  --location="$REGION" --policy=infra/cleanup-policy.json
```

## 4. Contas de serviço

Duas contas, cada uma só com o que precisa: uma para a esteira publicar, outra
para o site rodar.

```bash
gcloud iam service-accounts create portfolio-deploy --display-name="Esteira do portfólio"
gcloud iam service-accounts create portfolio-run --display-name="Site do portfólio"

DEPLOY_SA="portfolio-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
RUN_SA="portfolio-run@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/artifactregistry.writer"
gcloud iam service-accounts add-iam-policy-binding "$RUN_SA" \
  --member="serviceAccount:${DEPLOY_SA}" --role="roles/iam.serviceAccountUser"
```

## 5. Chave secreta do Django

Rode na pasta do projeto (`uv run` usa o Python do projeto; no Windows o
`python` do Git Bash pode ser outro, ou nenhum).

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(64), end='')" \
  | gcloud secrets create django-secret-key --data-file=-

gcloud secrets add-iam-policy-binding django-secret-key \
  --member="serviceAccount:${RUN_SA}" --role="roles/secretmanager.secretAccessor"
```

## 6. Login da esteira sem chave (Workload Identity Federation)

O GitHub prova ao Google que é o seu repositório; nenhuma chave fica guardada
no GitHub.

```bash
gcloud iam workload-identity-pools create github --location=global

gcloud iam workload-identity-pools providers create-oidc github \
  --location=global --workload-identity-pool=github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${REPO}'"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/${REPO}"

echo "GCP_WORKLOAD_IDENTITY_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github"
```

## 7. Variáveis no GitHub

No repositório: **Settings → Secrets and variables → Actions → aba Variables**.
São variáveis, não segredos: nenhuma é sigilosa.

| Variável | Valor |
|---|---|
| `GCP_PROJECT_ID` | o `PROJECT_ID` escolhido |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | a linha impressa no passo 6 |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `portfolio-deploy@<PROJECT_ID>.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | `portfolio-run@<PROJECT_ID>.iam.gserviceaccount.com` |
| `SITE_HOSTS` | `.run.app` (por enquanto; o domínio entra no passo 9) |

## 8. Primeira publicação

Rode a esteira de novo (aba **Actions → Pipeline → Re-run all jobs**) ou faça
um push na `main`. Com `GCP_PROJECT_ID` cadastrada, o job de deploy deixa de
ser pulado. No fim ele imprime o endereço `https://portfolio-....run.app`.

O site sobe sem o formulário de contato, só com os links: o formulário aparece
quando o e-mail for configurado (passo 10).

## 9. Domínio próprio

Para um domínio já registrado no <https://registro.br>. Os registros DNS deste
passo são criados no painel do próprio Registro.br, na edição da zona DNS do
domínio (modo avançado). Se o domínio usa servidores DNS de outro lugar, crie
os registros lá.

> **Antes de mexer no DNS**, anote os registros que o domínio já tem (`MX` de
> e-mail, `TXT`, outros sites) e não apague nenhum. Aqui só se acrescentam
> registros.

> **HTTPS em todos os subdomínios.** O site manda os navegadores usarem só
> HTTPS no domínio e em todos os subdomínios por um ano (HSTS, em
> `config/settings.py`). Um subdomínio servido em HTTP puro deixa de abrir para
> quem já visitou o site. Se houver algum, mude `SECURE_HSTS_INCLUDE_SUBDOMAINS`
> para `False` antes de ligar o domínio.

1. Provar ao Google que o domínio é seu. Sem isso o passo 2 é recusado.

   ```bash
   DOMAIN="seudominio.com.br"
   gcloud domains verify "$DOMAIN"
   ```

   O comando abre o Search Console. Escolha a verificação por registro `TXT`,
   crie no DNS o registro indicado (`google-site-verification=...`) e clique em
   verificar. Confira com `gcloud domains list-user-verified`.
2. Ligar o domínio ao serviço:

   ```bash
   gcloud beta run domain-mappings create --service portfolio --domain "$DOMAIN" --region "$REGION"
   gcloud beta run domain-mappings create --service portfolio --domain "www.${DOMAIN}" --region "$REGION"
   ```

   Cada comando lista registros DNS (`A`/`AAAA` para o domínio, `CNAME` para o
   `www`). Crie todos no DNS.
3. O certificado HTTPS leva de minutos a algumas horas. Acompanhe os dois
   endereços, até `https://seudominio.com.br` e `https://www.seudominio.com.br`
   abrirem no navegador:

   ```bash
   gcloud beta run domain-mappings describe --domain "$DOMAIN" --region "$REGION"
   gcloud beta run domain-mappings describe --domain "www.${DOMAIN}" --region "$REGION"
   ```

4. Só então, no GitHub, mudar `SITE_HOSTS` e criar `SITE_CANONICAL_HOST`, e
   rodar a esteira:

   | Variável | Valor |
   |---|---|
   | `SITE_HOSTS` | `seudominio.com.br,www.seudominio.com.br,.run.app` |
   | `SITE_CANONICAL_HOST` | `seudominio.com.br` |

   `SITE_CANONICAL_HOST` é o endereço principal: o `www` e o endereço
   `.run.app` passam a redirecionar para ele. Cadastrada antes de o
   certificado ficar pronto, ela manda os visitantes para um endereço que ainda
   não abre.
5. Conferir:

   ```bash
   # 200
   curl --silent --output /dev/null --write-out '%{http_code}\n' "https://${DOMAIN}/"
   # 301 https://seudominio.com.br/en/
   curl --silent --output /dev/null --write-out '%{http_code} %{redirect_url}\n' "https://www.${DOMAIN}/en/"
   ```

Alternativa para o DNS: conta gratuita no Cloudflare, trocando no Registro.br
os servidores DNS pelos dois que ele indicar. Nesse caso crie os registros com
o proxy **desligado** (nuvem cinza, "DNS only"): com o proxy ligado o Google
não consegue emitir o certificado.

## 10. E-mail do formulário de contato

Qualquer provedor SMTP serve. Com o Resend (plano gratuito):

1. Criar conta em <https://resend.com>, adicionar o domínio e criar no
   Cloudflare os registros DNS que ele pedir.
2. Criar uma chave de API e guardá-la como segredo:

   ```bash
   printf '%s' 're_SUA_CHAVE' | gcloud secrets create email-host-password --data-file=-
   gcloud secrets add-iam-policy-binding email-host-password \
     --member="serviceAccount:${RUN_SA}" --role="roles/secretmanager.secretAccessor"
   ```

3. No GitHub, cadastrar as variáveis e rodar a esteira:

   | Variável | Valor |
   |---|---|
   | `EMAIL_HOST` | `smtp.resend.com` |
   | `EMAIL_HOST_USER` | `resend` |
   | `DEFAULT_FROM_EMAIL` | `Portfólio <contato@seudominio.com.br>` |
   | `CONTACT_TO_EMAIL` | o e-mail onde você quer receber as mensagens |

4. Enviar uma mensagem de teste pelo site e conferir que chegou.

## 11. Opcional: primeiro acesso sem espera

O serviço dorme sem visitas e leva alguns segundos para acordar. Um ping a cada
10 minutos o mantém acordado, dentro do nível gratuito (3 jobs do Cloud
Scheduler):

```bash
gcloud services enable cloudscheduler.googleapis.com
gcloud scheduler jobs create http portfolio-acordado --location="$REGION" \
  --schedule="*/10 * * * *" --uri="https://seudominio.com.br/healthz" --http-method=GET
```
