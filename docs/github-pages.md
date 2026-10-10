# Publicação no GitHub Pages

O site não tem servidor. O Django é usado como **gerador**: o comando
`build_static` renderiza cada página uma vez e escreve o resultado em `dist/`,
que a esteira envia para o GitHub Pages.

```
dist/index.html      página inicial, em português
dist/en/index.html   a mesma página em inglês
dist/es/index.html   e em espanhol
dist/404.html        o que o Pages responde para um endereço que não existe
dist/robots.txt      dist/sitemap.xml
dist/static/...      CSS, JavaScript, fontes e imagens
dist/CNAME           o domínio, para o Pages não descartá-lo a cada deploy
dist/.nojekyll       publica os arquivos como estão, sem passar pelo Jekyll
```

## Gerar o site na máquina

```powershell
$env:DJANGO_STATIC_BUILD = "1"
uv run python manage.py build_static
```

Para conferir o resultado como o visitante vê, sirva a pasta como arquivos —
abrir `dist/index.html` direto no navegador quebra os caminhos `/static/`:

```powershell
uv run python -m http.server 8000 --directory dist
```

Durante o desenvolvimento siga usando `uv run python manage.py runserver`:
é o mesmo código, com recarregamento automático.

## Ligar o Pages no repositório (uma vez)

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
   Sem isso o job `deploy` falha; o `build` continua passando.
2. **Settings → Pages → Custom domain:** `viniciussilvadev.com.br`.
   Marque **Enforce HTTPS** depois que o certificado for emitido (alguns
   minutos; o GitHub emite sozinho, via Let's Encrypt).

## DNS do domínio

No painel do registrador do `viniciussilvadev.com.br`:

| Tipo  | Nome  | Valor                      |
| ----- | ----- | -------------------------- |
| A     | `@`   | `185.199.108.153`          |
| A     | `@`   | `185.199.109.153`          |
| A     | `@`   | `185.199.110.153`          |
| A     | `@`   | `185.199.111.153`          |
| CNAME | `www` | `viniciussilva2.github.io.` |

Os quatro registros `A` são o apex (`viniciussilvadev.com.br`); o `CNAME` faz
`www.` chegar no mesmo site, e o próprio Pages redireciona `www` para o apex —
é por isso que o site não precisa mais do middleware que fazia isso.

Confira a propagação antes de marcar *Enforce HTTPS*:

```powershell
nslookup viniciussilvadev.com.br
```

## Trocar de domínio

`SITE_URL` é a única fonte do endereço: entra no link canônico, nos `hreflang`,
no `sitemap.xml`, no JSON-LD e no `CNAME`. Para trocar, cadastre
**Settings → Secrets and variables → Actions → Variables → `SITE_URL`**
(ex.: `https://outro-dominio.com.br`) e ajuste o *Custom domain* e o DNS. Nada
no código precisa mudar.

## O que o Pages não faz

| Protege contra     | Como era (Cloud Run)         | Como é agora                        |
| ------------------ | ---------------------------- | ----------------------------------- |
| Conteúdo de fora   | header `Content-Security-Policy` | `<meta>` em cada página, de `SECURE_CSP` |
| Site dentro de um iframe | `X-Frame-Options`, `frame-ancestors` | sem proteção: só funcionam como header |
| HTTP em claro      | `SECURE_SSL_REDIRECT`, HSTS  | *Enforce HTTPS* do Pages (sem HSTS) |

Nenhuma delas protegia dados do visitante: o site não tem login, sessão,
cookie nem formulário. O que se perde é a defesa contra o site ser embutido em
um iframe de terceiros.
