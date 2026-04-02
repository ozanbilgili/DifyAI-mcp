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

## Özellikler

- **Dify-as-Code:** Workflow'ları YAML olarak çek, düzenle, geri yükle — Git ile versiyon kontrolü yap
- **Tek komutla test:** Workflow'u veya tekil node'ları test modunda çalıştır, sonuçları anında gör
- **Toplu test:** Birden fazla test case'i tek seferde çalıştır, başarı oranını karşılaştır
- **Knowledge Base yönetimi:** Dataset oluştur, doküman yükle, RAG retrieval'ı test et
- **Model & Tool yönetimi:** Model provider'ları ve tool'ları listele, default model'i ayarla
- **İstatistik & Loglar:** Token maliyeti, günlük kullanım, yanıt süresi, hata oranları
- **Sağlık kontrolü:** Tüm app'lerin durumunu tek seferde kontrol et
- **DSL karşılaştırma:** İki YAML sürümünü diff ile karşılaştır
- **Toplu dışa aktarma:** Tüm app'leri YAML dosyalarına export et

## MCP Araçları (52 Tool)

### Uygulama Yönetimi
| Araç | Açıklama |
|---|---|
| `list_apps` | Tüm uygulamaları listeler (sayfalama + filtreleme) |
| `get_app_detail` | Uygulama detaylarını getirir |
| `create_app` | Yeni boş uygulama oluşturur |
| `delete_app` | Uygulamayı siler |
| `copy_app` | Mevcut uygulamayı kopyalar |

### DSL Export / Import
| Araç | Açıklama |
|---|---|
| `get_app_dsl` | Workflow'u YAML DSL olarak export eder |
| `update_app_dsl` | YAML DSL'i Dify'a import/update eder |

### Workflow Yönetimi
| Araç | Açıklama |
|---|---|
| `get_workflow_draft` | Draft graf yapısını (node'lar, edge'ler) getirir |
| `publish_workflow` | Draft'ı aktif sürüm olarak yayınlar |
| `list_workflow_versions` | Tüm yayınlanmış workflow sürümlerini listeler |
| `restore_workflow_version` | Eski bir sürümü geri yükler |
| `run_workflow_test` | Draft workflow'u test modunda çalıştırır |
| `run_single_node` | Tekil bir node'u test eder |
| `stop_workflow_task` | Çalışan workflow'u durdurur |
| `get_default_block_configs` | Node tiplerine göre varsayılan konfigürasyonları getirir |

### Loglar & Çalışma Geçmişi
| Araç | Açıklama |
|---|---|
| `get_workflow_runs` | Workflow çalışma geçmişini listeler |
| `get_workflow_run_detail` | Belirli bir çalışmanın detayını getirir |
| `get_node_executions` | Node bazında çalışma detaylarını getirir |
| `get_workflow_app_logs` | Uygulama loglarını getirir |

### İstatistikler
| Araç | Açıklama |
|---|---|
| `get_app_statistics` | Mesaj, kullanıcı, token, maliyet, yanıt süresi istatistikleri |
| `get_workflow_statistics` | Workflow'a özel çalışma ve maliyet istatistikleri |

### Knowledge Base (Bilgi Tabanı)
| Araç | Açıklama |
|---|---|
| `list_datasets` | Tüm dataset'leri listeler |
| `create_dataset` | Yeni dataset oluşturur |
| `get_dataset_detail` | Dataset detaylarını getirir |
| `delete_dataset` | Dataset'i siler |
| `list_documents` | Dataset'teki dokümanları listeler |
| `get_document_segments` | Doküman chunk'larını listeler |
| `get_dataset_indexing_status` | İndeksleme durumunu gösterir |
| `hit_testing` | RAG retrieval testi — sorgu ile eşleşen chunk'ları bulur |
| `get_dataset_related_apps` | Dataset'i kullanan uygulamaları gösterir |

### Model Provider Yönetimi
| Araç | Açıklama |
|---|---|
| `list_model_providers` | Tüm model sağlayıcılarını listeler |
| `get_provider_models` | Bir sağlayıcının modellerini listeler |
| `get_default_model` | Varsayılan modeli gösterir |
| `set_default_model` | Varsayılan modeli ayarlar |

### Tool Provider Yönetimi
| Araç | Açıklama |
|---|---|
| `list_tool_providers` | Tüm tool sağlayıcılarını listeler |
| `list_builtin_tools` | Bir sağlayıcının araçlarını listeler |
| `list_workflow_tools` | Workflow-as-tool tanımlarını listeler |

### Ortam Değişkenleri
| Araç | Açıklama |
|---|---|
| `get_environment_variables` | Workflow env var'larını getirir |
| `get_conversation_variables` | Konuşma değişkenlerini getirir |

### API Key Yönetimi
| Araç | Açıklama |
|---|---|
| `list_app_api_keys` | Uygulama API key'lerini listeler |
| `create_app_api_key` | Yeni API key oluşturur |
| `delete_app_api_key` | API key'i siler |

### Etiketler
| Araç | Açıklama |
|---|---|
| `list_tags` | Tüm etiketleri listeler |
| `create_tag` | Yeni etiket oluşturur |

### Konuşmalar & Mesajlar
| Araç | Açıklama |
|---|---|
| `list_conversations` | Chat konuşmalarını listeler |
| `list_messages` | Mesajları listeler |

### Erişim Kontrolü
| Araç | Açıklama |
|---|---|
| `toggle_app_site` | Web arayüzü erişimini aç/kapa |
| `toggle_app_api` | API erişimini aç/kapa |

### Üst Seviye Araçlar
| Araç | Açıklama |
|---|---|
| `dsl_diff` | İki YAML DSL'i karşılaştırır, farkları gösterir |
| `batch_test` | Birden fazla test case'i toplu çalıştırır |
| `health_check` | Tüm app'lerin durumunu ve hata oranlarını kontrol eder |
| `export_all_apps_dsl` | Tüm uygulamaları YAML dosyalarına toplu export eder |

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
