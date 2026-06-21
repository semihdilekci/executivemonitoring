# Infra (AWS CDK)

YGIP dev ortamı kaynakları AWS CDK (Python) ile tanımlanır. Kaynak adlandırma: `dev-ygip-{service}` (`30-infra-aws`).

## Kaynaklar (dev)

| Kaynak | Ad / not |
|--------|----------|
| VPC | `dev-ygip-vpc` — izole subnet, NAT yok (maliyet) |
| RDS PostgreSQL 16 | `dev-ygip-rds` — t3.micro, VPC-internal, backup kapalı |
| S3 | `dev-ygip-archive-{account}` — ham arşiv + digest HTML |
| SQS + DLQ | `dev-ygip-sqs-{rss,email,gov,api}` + `-dlq` |
| EventBridge | `dev-ygip-collector-schedule-{rss,email,gov}` — 15/60/30 dk |
| Lambda | `dev-ygip-collector-{rss,email,gov}` — collector worker'lar (bundle artifact, VPC-internal) |
| CloudWatch | `/aws/lambda/dev-ygip-collector-*` log grupları |
| IAM | `dev-ygip-lambda-execution` — dev kaynakları + prod deny |
| Security Group | `dev-ygip-lambda-sg` — collector Lambda VPC-internal RDS erişimi |

**E-posta (SMTP):** AWS SES kullanılmaz. Dev'de Gmail SMTP (`smtp.gmail.com:587`, uygulama şifresi); production'da kurumsal SMTP relay. Kimlik bilgileri `.env` / Secrets Manager'da — IaC dışı.

**Redis:** MVP-0 dev'de Upstash (serverless); ElastiCache bu stack'te yok. `REDIS_URL` `.env` / Secrets Manager'dan.

**pgvector:** RDS'de migration `002_data_tables.py` ile `CREATE EXTENSION vector` uygulanır.

## Önkoşullar

- Python 3.12+
- Node.js 18+ (CDK CLI)
- AWS CLI yapılandırılmış (`aws configure` veya SSO)

```bash
npm install -g aws-cdk
pip install -r infra/requirements.txt
```

## Synth (yerel, deploy yok)

```bash
cd infra
pip install -r requirements.txt
cdk synth          # veya: npx aws-cdk synth
```

CI / test:

```bash
pip install -r requirements-dev.txt
pytest tests/unit/infra/test_stack_synth.py -v
```

## Deploy (dev)

> **Uyarı:** Gerçek AWS kaynakları oluşturur; maliyet doğar. Production deploy MVP-1'de.

**Önkoşul (Faz 8.3):** Collector Lambda gerçek bundle artifact kullanır — `cdk deploy`
öncesi bundle build edilmeli ve secret'lar deploy-time export edilmeli. Bundle dizini
(`dist/lambda/collector/`) yoksa CDK synth placeholder stub'a düşer (501 döner).

```bash
# 1) Collector bundle artifact (linux wheel için CI runner veya cross-compile flag)
LAMBDA_TARGET_PLATFORM=1 ./scripts/build_lambda.sh collector

# 2) Deploy-time secret/param (commit edilmez — `.env` veya CI secret'tan)
export DATABASE_URL="postgresql+asyncpg://..."   # RdsSecretArn'dan türetilir
export REDIS_URL="rediss://..."                  # Upstash

cd infra
cdk bootstrap aws://ACCOUNT_ID/eu-west-1   # hesapta bir kez
cdk deploy
```

Deploy sonrası çıktılar (`cdk deploy` Outputs):

- `ArchiveBucketName` → `S3_ARCHIVE_BUCKET`
- `Sqs{Rss,Email,Gov,Api}Url` → `SQS_QUEUE_*_URL`
- `RdsEndpoint` + `RdsSecretArn` → `DATABASE_URL` (Secrets Manager'dan)
- `LambdaExecutionRoleArn` — Faz 2+ Lambda deploy
- `Collector{Rss,Email,Gov}Arn` — collector Lambda ARN'leri

### Collector Lambda (manuel invoke)

Deploy sonrası tek collector tipini test etmek için:

```bash
aws lambda invoke \
  --function-name dev-ygip-collector-rss \
  --payload '{"source_type":"rss"}' \
  /tmp/collector-out.json
cat /tmp/collector-out.json
```

> **Not:** CDK `Code.from_asset` öncelikle bundle dizinini (`dist/lambda/collector/`,
> `scripts/build_lambda.sh` çıktısı) kullanır; yalnızca bundle build edilmemişse (CI synth)
> `infra/collectors/lambda_stub/` placeholder'ına düşer. Handler her durumda
> `services.collectors.handler.lambda_handler` — per-tip legacy handler'lar kaldırıldı
> (Faz 8.3).

### Processor Lambda (SQS triggered)

`dev-ygip-processor-{rss,email,gov}` Lambda'ları ilgili `dev-ygip-sqs-{type}`
kuyruğunu **SQS event source mapping** ile otomatik tüketir (Faz 8.4) — manuel
invoke gerekmez; collector mesaj yazınca processor tetiklenir. Handler
`services.processor.handlers.processor_handler.lambda_handler`, bundle
`dist/lambda/processor/` (`scripts/build_lambda.sh processor`); bundle yoksa
`infra/processor/lambda_stub/` placeholder'ına düşer.

- **Partial batch failure:** event source mapping `ReportBatchItemFailures`
  açık; handler yalnızca başarısız mesajları `batchItemFailures` ile geri verir,
  kalanlar silinir.
- **DLQ redrive:** ana kuyruğun `max_receive_count=3` redrive policy'si 3.
  denemeden sonra mesajı `dev-ygip-sqs-{type}-dlq`'ya taşır (`Docs/04` §8.7).
- **Profil:** `memory=512 MB`, `timeout=120 s` (embedding CPU/I/O); queue
  visibility timeout (5 dk) > Lambda timeout.
- **Env:** `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY` (boşsa deterministic
  embedding fallback), `ENVIRONMENT` — collector ile aynı VPC/SG/role.

## Dev deploy workflow (Faz 8.5)

`.github/workflows/deploy-dev.yml` dev stack'i (`YgipDevStack`) **manuel** deploy
eder — maliyet kontrolü için yalnızca `workflow_dispatch`, otomatik push tetikleme
yok. Production (`prod-ygip-*`) deploy MVP-1'e ertelendi.

GitHub → **Actions** → **Deploy Dev** → **Run workflow**:

| Input | Etki |
|-------|------|
| `run_smoke` | Deploy sonrası `smoke_pipeline_dev.sh` çalıştırır (rss) |
| `bootstrap` | İlk deploy için `cdk bootstrap` (hesapta bir kez) |

Workflow adımları: checkout → `build_lambda.sh collector|processor` (linux runner,
cross-compile gerekmez) → `cdk deploy YgipDevStack --require-approval never`.

Gerekli repo secret'ları (Settings → Secrets → Actions, `dev` environment):

| Secret | Kullanım |
|--------|----------|
| `AWS_DEV_DEPLOY_ROLE_ARN` | OIDC ile üstlenilen dev deploy rolü (statik anahtar yok) |
| `DEV_DATABASE_URL` | Lambda runtime `DATABASE_URL` (CDK synth-time enjekte) |
| `DEV_REDIS_URL` | Lambda runtime `REDIS_URL` |

> **VPC egress dikkat:** Dev VPC NAT'sız izole subnet. Collector Lambda harici
> RSS/SMTP fetch ve SQS publish için internet/VPC endpoint ister; smoke öncesi
> SQS/Secrets Manager interface endpoint veya geçici NAT değerlendirilir.

## Pipeline smoke (Faz 8.5)

`scripts/smoke_pipeline_dev.sh` deploy sonrası `collector → SQS → processor → DB`
akışını doğrular: collector Lambda invoke → SQS depth gözlem → processor
(SQS-triggered) tüketimi → DLQ kontrolü → `raw_items`/`processed_items` satır artışı.

```bash
./scripts/smoke_pipeline_dev.sh                    # rss, tam akış (AWS gerekir)
./scripts/smoke_pipeline_dev.sh --source-type gov
./scripts/smoke_pipeline_dev.sh --skip-db          # RDS VPC-internal erişilemez ise
./scripts/smoke_pipeline_dev.sh --dry-run          # AWS yok — komut akışını yazdır
```

| Flag | Etki |
|------|------|
| `--source-type rss\|email\|gov` | Hangi collector/queue (varsayılan `rss`) |
| `--wait <sn>` | Processor tüketim bekleme süresi (varsayılan 45 s) |
| `--skip-db` | DB doğrulamasını atla (`DATABASE_URL` yoksa otomatik) |
| `--dry-run` | Gerçek AWS çağrısı yapmadan komutları yazdır |

DB doğrulaması için `DATABASE_URL` + `psql` gerekir; RDS VPC-internal olduğundan
CI/yerelden erişilemezse `--skip-db` ile SQS/DLQ gözlemi yeterlidir (DB artışı
bastion/SSM tüneli ile manuel doğrulanır). Çıkış kodu: 0 başarı, 1 başarısızlık
(DLQ'ya mesaj düşmesi veya satır artmaması).

## Lambda Bundle (Faz 8.2)

`scripts/build_lambda.sh`, `services/` + `packages/` + runtime bağımlılıklarını tek bir deploy artifact'ına paketler.

```bash
./scripts/build_lambda.sh collector    # → dist/lambda/collector.zip
./scripts/build_lambda.sh processor    # → dist/lambda/processor.zip
```

Handler giriş noktaları (CDK `handler` parametresi):

| Target | Handler |
|--------|---------|
| collector | `services.collectors.handler.lambda_handler` |
| processor | `services.processor.handlers.processor_handler.lambda_handler` |

Bundle değişkenleri:

| Değişken | Etki |
|----------|------|
| `BUNDLE_SKIP_DEPS=1` | pip vendoring atlanır — offline smoke / hızlı test (CI unit) |
| `LAMBDA_TARGET_PLATFORM=1` | macOS host → Lambda linux `manylinux2014_x86_64` cross-compile (asyncpg, cryptography wheel'leri) |

> **Cross-compile:** macOS'ta yerel `pip install -t` Lambda linux runtime ile uyumsuz binary wheel üretebilir. Deploy bundle'ı **linux runner'da** (CI) veya `LAMBDA_TARGET_PLATFORM=1` ile üretin. Bundle boyutu 250 MB unzipped limitine tabi — `fastapi`/`uvicorn`/`alembic` artifact'tan hariç tutulur.

Artifact (`dist/lambda/`) git-ignore'lu (`.gitignore` → `dist/`).

### Lambda runtime ortam değişkenleri

CDK deploy-time enjekte eder (`Docs/09` §7); secret'lar Secrets Manager / `.env` üzerinden:

| Değişken | Kullanım |
|----------|----------|
| `DATABASE_URL` | RDS PostgreSQL (asyncpg) |
| `REDIS_URL` | Upstash dedup / idempotency |
| `SQS_QUEUE_{RSS,EMAIL,GOV,API}_URL` | collector publish / processor trigger |
| `S3_ARCHIVE_BUCKET` | ham arşiv |
| `AWS_REGION` | `eu-west-1` |
| `ENCRYPTION_KEY` | collector secret çözme |
| `OPENAI_API_KEY` | processor embedding (yoksa deterministic fallback) |

### SQS → raw_items (Faz 2.6)

Collector mesajı SQS'e yazar; `services/collectors/persistence.py` mesajı Redis dedup + `raw_items` insert ile işler (Faz 3 processor öncesi stub).

SMTP için `.env` örneği (dev Gmail):

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=                    # Google uygulama şifresi
SMTP_FROM_EMAIL=you@gmail.com
SMTP_USE_TLS=true
```

## Ortam izolasyonu (`Docs/09` §7.3)

- [x] Lambda role yalnızca `dev-ygip-*` SQS/S3 ve `ygip/dev/*` secret'lara izin
- [x] IAM deny: `prod-ygip-*`, `ygip-prod-*`, `ygip/prod/*`
- [x] RDS `publicly_accessible=false`
- [x] Collector Lambda VPC-internal (`dev-ygip-lambda-sg`) — RDS'e VPC CIDR üzerinden erişir
- [ ] Dev'den prod RDS — network + IAM ile ayrı hesap/VPC önerilir (manuel checklist)

> **VPC egress (Faz 8.5 dikkat):** Dev VPC NAT'sız izole subnet (maliyet). Collector
> Lambda VPC-internal RDS'e erişir, ancak harici RSS/SMTP fetch ve SQS publish için
> internet/VPC endpoint gerekir. Dev smoke'ta SQS/Secrets Manager interface endpoint
> veya NAT eklenmesi Faz 8.5 deploy adımında değerlendirilir.

## Agent kısıtı

`cdk destroy` veya AWS kaynak silme komutları **kullanıcı onayı olmadan** çalıştırılmaz (`Docs/09` §6.1).

Detay: `Docs/10_IMPLEMENTATION_ROADMAP.md` §0.6, `.cursor/rules/30-infra-aws.mdc`
