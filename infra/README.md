# Infra (AWS CDK)

YGIP dev ortamı kaynakları AWS CDK (Python) ile tanımlanır. Kaynak adlandırma: `dev-ygip-{service}` (`30-infra-aws`).

## Kaynaklar (dev)

| Kaynak | Ad / not |
|--------|----------|
| VPC | `dev-ygip-vpc` — izole subnet, NAT yok (maliyet) |
| RDS PostgreSQL 16 | `dev-ygip-rds` — t3.micro, VPC-internal, backup kapalı |
| S3 | `dev-ygip-archive-{account}` — ham arşiv + digest HTML |
| SQS + DLQ | `dev-ygip-sqs-{rss,email,gov,api}` + `-dlq` |
| EventBridge | `dev-ygip-collector-schedule-placeholder` (disabled) |
| IAM | `dev-ygip-lambda-execution` — dev kaynakları + prod deny |

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

> **Uyarı:** Gerçek AWS kaynakları oluşturur; maliyet doğar. Production deploy Faz 8'de.

```bash
cd infra
cdk bootstrap aws://ACCOUNT_ID/eu-west-1   # hesapta bir kez
cdk deploy
```

Deploy sonrası çıktılar (`cdk deploy` Outputs):

- `ArchiveBucketName` → `S3_ARCHIVE_BUCKET`
- `Sqs{Rss,Email,Gov,Api}Url` → `SQS_QUEUE_*_URL`
- `RdsEndpoint` + `RdsSecretArn` → `DATABASE_URL` (Secrets Manager'dan)
- `LambdaExecutionRoleArn` — Faz 2+ Lambda deploy

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
- [ ] Dev'den prod RDS — network + IAM ile ayrı hesap/VPC önerilir (manuel checklist)

## Agent kısıtı

`cdk destroy` veya AWS kaynak silme komutları **kullanıcı onayı olmadan** çalıştırılmaz (`Docs/09` §6.1).

Detay: `Docs/10_IMPLEMENTATION_ROADMAP.md` §0.6, `.cursor/rules/30-infra-aws.mdc`
