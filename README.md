# OpenFDA Drug Integration API

![CI Tests](https://github.com/guirediss/fdaConsumer/actions/workflows/test.yml/badge.svg)

## Visão geral

Aplicação backend desenvolvida para uma avaliação técnica. Ela extrai bulas de medicamentos da API pública OpenFDA, persiste os dados em PostgreSQL e disponibiliza operações de extração e consulta por uma API REST. A aplicação e o banco são executados em containers Docker coordenados pelo Docker Compose.

## Requisitos atendidos

- **Extração de dados via API:** consulta a `https://api.fda.gov/drug/label.json` com os parâmetros dinâmicos `search` e `limit`, além de suporte opcional à autenticação por API Key.
- **Armazenamento relacional:** persistência estruturada na tabela `drug_labels`, usando `set_id` como identificador único para atualizar registros existentes sem criar duplicatas em extrações repetidas.
- **Acesso remoto via API REST:** endpoints implementados com FastAPI e documentados interativamente pelo Swagger UI em `/docs`.
- **Conteinerização:** ambiente reproduzível com Docker Compose, incluindo a API Python e o PostgreSQL com healthcheck.
- **Controle de versão:** histórico organizado em commits atômicos seguindo padrões convencionais.

## Arquitetura e estrutura

```text
app/
├── config.py             # Configurações carregadas do ambiente
├── database.py           # Engine, sessão SQLAlchemy e base declarativa
├── main.py               # Aplicação FastAPI, lifespan e healthcheck
├── models.py             # Modelo relacional DrugLabel
├── routers/
│   └── drugs.py          # Endpoints de extração e consulta
├── schemas.py            # Schemas de entrada e saída
└── services/
    └── openfda.py        # Cliente HTTP e normalização da OpenFDA
tests/
├── conftest.py           # Fixtures com SQLite isolado
└── test_drugs.py         # Testes dos endpoints e persistência
```

## Configuração e execução

### Pré-requisitos

- Docker instalado e em execução.
- Docker Compose v2 (`docker compose`).
- Git.

### 1. Clonar o repositório

```bash
git clone https://github.com/guirediss/fdaConsumer.git
cd fdaConsumer
```

### 2. Configurar as variáveis de ambiente

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Abra `.env` e, se desejar, informe uma chave no campo `OPENFDA_API_KEY`. É possível solicitar uma chave gratuita no [portal oficial de autenticação da OpenFDA](https://open.fda.gov/apis/authentication/). A aplicação também funciona sem chave, sujeita aos limites mais restritos de acesso da API.

As variáveis `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB` configuram o banco. `DATABASE_URL` é opcional; se não for informada, a aplicação monta a URL usando as variáveis do PostgreSQL. `OPENFDA_BASE_URL` define o endpoint consultado.

### 3. Subir o ambiente

Na raiz do projeto, execute:

```bash
docker compose up --build -d
```

O Compose aguarda o healthcheck do PostgreSQL antes de iniciar a API. Na inicialização, a aplicação cria a tabela necessária. Para conferir o estado dos serviços:

```bash
docker compose ps
```

Para acompanhar os logs:

```bash
docker compose logs -f api
```

Para parar os serviços sem remover os dados persistidos:

```bash
docker compose down
```

O banco usa o volume nomeado `postgres_data`. Removê-lo com `docker compose down -v` também apaga os dados armazenados.

## Acessar e testar a API

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

### Extrair e persistir bulas

`POST /api/v1/drugs/extract` consulta a OpenFDA e insere ou atualiza as bulas retornadas. `generic_name` é obrigatório; `limit` é opcional e varia de 1 a 25.

```bash
curl -X POST "http://localhost:8000/api/v1/drugs/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "generic_name": "sertraline",
    "limit": 5
  }'
```

A API retorna a quantidade extraída e os registros persistidos. Retorna `404` quando nenhuma bula é encontrada e `502` quando ocorre uma falha de integração com a OpenFDA.

### Consultar registros com filtro e paginação

`GET /api/v1/drugs` aceita `generic_name`, `skip` e `limit` como parâmetros opcionais.

```bash
curl "http://localhost:8000/api/v1/drugs?generic_name=sertraline&skip=0&limit=20"
```

### Buscar um registro pelo ID

`GET /api/v1/drugs/{drug_id}` consulta um registro pelo ID interno do banco:

```bash
curl "http://localhost:8000/api/v1/drugs/1"
```

Se o ID não existir, a API retorna `404`.

## Testes automatizados

Com os serviços ativos, execute a suíte dentro do container da API:

```bash
docker compose exec api pytest -v
```

Os testes usam um banco SQLite em memória e simulam as respostas da OpenFDA; não dependem de chamadas de rede reais nem alteram o PostgreSQL da aplicação.
