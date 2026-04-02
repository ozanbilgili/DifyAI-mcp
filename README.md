# Dify Management MCP Server

Dify AI iş akışlarını (workflow) Claude Code terminalinden yönetmek için MCP (Model Context Protocol) sunucusu.

Dify'ın görsel arayüzüne gerek kalmadan, Claude Code ile doğrudan workflow oluşturma, düzenleme, test etme ve yayınlama işlemlerini gerçekleştirebilirsiniz.

## Gereksinimler

- [uv](https://docs.astral.sh/uv/) (Python paket yöneticisi)
- [Claude Code](https://claude.ai/claude-code) CLI
- Çalışan bir [Dify](https://github.com/langgenius/dify) instance'ı (Docker Compose ile)

## Kurulum

### 1. Repo'yu klonla

```bash
git clone <repo-url> dify-mcp-server
cd dify-mcp-server
```

### 2. uv kur (yoksa)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Dify'da Admin API Key aktif et

Dify'ın `docker/.env` dosyasına ekle:

```ini
ADMIN_API_KEY_ENABLE=true
ADMIN_API_KEY=<guclu-bir-anahtar-olustur>
```

Anahtar oluşturmak için:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Önemli:** Dify'ın `docker/docker-compose.yaml` dosyasında `x-shared-env` bloğunun içine şu iki satırı ekle (yoksa env değişkenleri container'a geçmez):

```yaml
x-shared-env: &shared-api-worker-env
  # ... mevcut değerler ...
  ADMIN_API_KEY_ENABLE: ${ADMIN_API_KEY_ENABLE:-false}
  ADMIN_API_KEY: ${ADMIN_API_KEY:-}
```

Sonra container'ları yeniden başlat:

```bash
cd docker
docker compose down && docker compose up -d
```

### 4. Workspace ID'ni öğren

Dify'a login olduktan sonra:

```bash
# Önce login ol (şifre base64 encoded olmalı)
B64PASS=$(echo -n "<sifren>" | base64)
curl -s -c /tmp/cookies.txt -X POST http://localhost/console/api/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"<email>\",\"password\":\"$B64PASS\"}"

# CSRF token'ı al
CSRF=$(grep csrf_token /tmp/cookies.txt | awk '{print $NF}')

# Workspace listesini çek
curl -s -b /tmp/cookies.txt "http://localhost/console/api/workspaces" \
  -H "X-Csrf-Token: $CSRF"
```

Çıktıdaki `"id"` değeri senin Workspace ID'n.

### 5. Claude Code'a MCP sunucusunu tanımla

`~/.claude.json` dosyasındaki `"mcpServers"` bölümüne ekle (veya proje-bazlı `settings.json`'a):

```json
{
  "mcpServers": {
    "dify-manager": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project", "/FULL/PATH/TO/dify-mcp-server",
        "python", "/FULL/PATH/TO/dify-mcp-server/server.py"
      ],
      "env": {
        "DIFY_BASE_URL": "http://localhost",
        "DIFY_ADMIN_API_KEY": "<senin-admin-api-key>",
        "DIFY_WORKSPACE_ID": "<senin-workspace-id>"
      }
    }
  }
}
```

> `/FULL/PATH/TO/dify-mcp-server` kısmını klonladığın dizinin tam yolu ile değiştir.

### 6. Claude Code'u yeniden başlat

```bash
claude
```

## Kullanım

Claude Code terminalinde doğal dilde komut verebilirsin:

```
> Dify'daki uygulamaları listele
> "Müşteri Destek" uygulamasını YAML olarak çek ve workflow.yaml'a kaydet
> Bu akışa bir Python node'u ekle, duygu analizi yapsın
> Değişiklikleri Dify'a gönder ve "Merhaba, çok sinirliydim!" girdisiyle test et
> Draft'ı yayınla
```

## MCP Araçları (Tools)

| Araç | Açıklama |
|---|---|
| `list_apps` | Tüm uygulamaları listeler (sayfalama + filtreleme) |
| `get_app_detail` | Uygulama detaylarını getirir |
| `get_app_dsl` | Workflow'u YAML DSL olarak export eder |
| `update_app_dsl` | YAML DSL'i Dify'a import/update eder |
| `run_workflow_test` | Draft workflow'u test modunda çalıştırır |
| `publish_workflow` | Draft'ı aktif sürüm olarak yayınlar |
| `get_workflow_draft` | Draft graf yapısını (node'lar, edge'ler) getirir |
| `create_app` | Yeni boş uygulama oluşturur |
| `delete_app` | Uygulamayı siler |

## Ortam Değişkenleri

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `DIFY_BASE_URL` | Hayır | `http://localhost` | Dify instance URL'i |
| `DIFY_ADMIN_API_KEY` | Evet | - | Dify Admin API anahtarı |
| `DIFY_WORKSPACE_ID` | Evet | - | Dify Workspace UUID'si |

## Mimari

```
Claude Code  <-->  MCP Server (stdio)  <-->  Dify Console API
                   (bu proje)                  (localhost/console/api)
                                                     |
                                                Dify Platform
                                              (Docker Compose)
```

MCP sunucusu, Dify Console API'sine `Authorization: Bearer <ADMIN_API_KEY>` + `X-WORKSPACE-ID` header'ları ile bağlanır. Cookie/CSRF gerektirmez.

## Sorun Giderme

**"ADMIN_API_KEY env var not found"**
- `settings.json`'daki `env` bloğunun doğru olduğunu kontrol et.

**"401 Unauthorized" / "Invalid token"**
- `docker-compose.yaml`'da `ADMIN_API_KEY` ve `ADMIN_API_KEY_ENABLE` satırlarının `x-shared-env` altında olduğundan emin ol.
- `docker compose down && docker compose up -d` ile yeniden başlat.
- Container içinde env'i kontrol et: `docker compose exec api env | grep ADMIN`

**"CSRF token is missing"**
- Admin API key doğru ayarlanmamış. Yukarıdaki adımları tekrar kontrol et.

## Lisans

MIT
