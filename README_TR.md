[English](README.md) | [**Turkce**](README_TR.md)

# Dify Management MCP Server

Dify AI is akislarini (workflow) Claude Code terminalinden yonetmek icin MCP (Model Context Protocol) sunucusu.

Dify'in gorsel arayuzune gerek kalmadan, Claude Code ile dogrudan workflow olusturma, duzenleme, test etme ve yayinlama islemlerini gerceklestirebilirsiniz.

## Gereksinimler

- [uv](https://docs.astral.sh/uv/) (Python paket yoneticisi)
- [Claude Code](https://claude.ai/claude-code) CLI
- Calisan bir [Dify](https://github.com/langgenius/dify) instance'i (Docker Compose ile)

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

Dify'in `docker/.env` dosyasina ekle:

```ini
ADMIN_API_KEY_ENABLE=true
ADMIN_API_KEY=<guclu-bir-anahtar-olustur>
```

Anahtar olusturmak icin:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Onemli:** Dify'in `docker/docker-compose.yaml` dosyasinda `x-shared-env` blogunun icerisine su iki satiri ekle (yoksa env degiskenleri container'a gecmez):

```yaml
x-shared-env: &shared-api-worker-env
  # ... mevcut degerler ...
  ADMIN_API_KEY_ENABLE: ${ADMIN_API_KEY_ENABLE:-false}
  ADMIN_API_KEY: ${ADMIN_API_KEY:-}
```

Sonra container'lari yeniden baslat:

```bash
cd docker
docker compose down && docker compose up -d
```

### 4. Workspace ID'ni ogren

Dify'a login olduktan sonra:

```bash
# Once login ol (sifre base64 encoded olmali)
B64PASS=$(echo -n "<sifren>" | base64)
curl -s -c /tmp/cookies.txt -X POST http://localhost/console/api/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"<email>\",\"password\":\"$B64PASS\"}"

# CSRF token'i al
CSRF=$(grep csrf_token /tmp/cookies.txt | awk '{print $NF}')

# Workspace listesini cek
curl -s -b /tmp/cookies.txt "http://localhost/console/api/workspaces" \
  -H "X-Csrf-Token: $CSRF"
```

Ciktidaki `"id"` degeri senin Workspace ID'n.

### 5. Claude Code'a MCP sunucusunu tanimla

`~/.claude.json` dosyasindaki `"mcpServers"` bolumune ekle (veya proje-bazli `settings.json`'a):

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

> `/FULL/PATH/TO/dify-mcp-server` kismini klonladigin dizinin tam yolu ile degistir.

### 6. Claude Code'u yeniden baslat

```bash
claude
```

## Kullanim

Claude Code terminalinde dogal dilde komut verebilirsin:

```
> Dify'daki uygulamalari listele
> "Musteri Destek" uygulamasini YAML olarak cek ve workflow.yaml'a kaydet
> Bu akisa bir Python node'u ekle, duygu analizi yapsin
> Degisiklikleri Dify'a gonder ve "Merhaba, cok sinirliydim!" girdisiyle test et
> Draft'i yayinla
```

## Ozellikler

- **Dify-as-Code:** Workflow'lari YAML olarak cek, duzenle, geri yukle — Git ile versiyon kontrolu yap
- **Tek komutla test:** Workflow'u veya tekil node'lari test modunda calistir, sonuclari aninda gor
- **Toplu test:** Birden fazla test case'i tek seferde calistir, basari oranini karsilastir
- **Knowledge Base yonetimi:** Dataset olustur, dokuman yukle, RAG retrieval'i test et
- **Model & Tool yonetimi:** Model provider'lari ve tool'lari listele, default model'i ayarla
- **Istatistik & Loglar:** Token maliyeti, gunluk kullanim, yanit suresi, hata oranlari
- **Saglik kontrolu:** Tum app'lerin durumunu tek seferde kontrol et
- **DSL karsilastirma:** Iki YAML surumunu diff ile karsilastir
- **Toplu disa aktarma:** Tum app'leri YAML dosyalarina export et

## MCP Araclari (52 Tool)

### Uygulama Yonetimi
| Arac | Aciklama |
|---|---|
| `list_apps` | Tum uygulamalari listeler (sayfalama + filtreleme) |
| `get_app_detail` | Uygulama detaylarini getirir |
| `create_app` | Yeni bos uygulama olusturur |
| `delete_app` | Uygulamayi siler |
| `copy_app` | Mevcut uygulamayi kopyalar |

### DSL Export / Import
| Arac | Aciklama |
|---|---|
| `get_app_dsl` | Workflow'u YAML DSL olarak export eder |
| `update_app_dsl` | YAML DSL'i Dify'a import/update eder |

### Workflow Yonetimi
| Arac | Aciklama |
|---|---|
| `get_workflow_draft` | Draft graf yapisini (node'lar, edge'ler) getirir |
| `publish_workflow` | Draft'i aktif surum olarak yayinlar |
| `list_workflow_versions` | Tum yayinlanmis workflow surumlerini listeler |
| `restore_workflow_version` | Eski bir surumu geri yukler |
| `run_workflow_test` | Draft workflow'u test modunda calistirir |
| `run_single_node` | Tekil bir node'u test eder |
| `stop_workflow_task` | Calisan workflow'u durdurur |
| `get_default_block_configs` | Node tiplerine gore varsayilan konfigurasyonlari getirir |

### Loglar & Calisma Gecmisi
| Arac | Aciklama |
|---|---|
| `get_workflow_runs` | Workflow calisma gecmisini listeler |
| `get_workflow_run_detail` | Belirli bir calismanin detayini getirir |
| `get_node_executions` | Node bazinda calisma detaylarini getirir |
| `get_workflow_app_logs` | Uygulama loglarini getirir |

### Istatistikler
| Arac | Aciklama |
|---|---|
| `get_app_statistics` | Mesaj, kullanici, token, maliyet, yanit suresi istatistikleri |
| `get_workflow_statistics` | Workflow'a ozel calisma ve maliyet istatistikleri |

### Knowledge Base (Bilgi Tabani)
| Arac | Aciklama |
|---|---|
| `list_datasets` | Tum dataset'leri listeler |
| `create_dataset` | Yeni dataset olusturur |
| `get_dataset_detail` | Dataset detaylarini getirir |
| `delete_dataset` | Dataset'i siler |
| `list_documents` | Dataset'teki dokumanlari listeler |
| `get_document_segments` | Dokuman chunk'larini listeler |
| `get_dataset_indexing_status` | Indeksleme durumunu gosterir |
| `hit_testing` | RAG retrieval testi — sorgu ile eslesen chunk'lari bulur |
| `get_dataset_related_apps` | Dataset'i kullanan uygulamalari gosterir |

### Model Provider Yonetimi
| Arac | Aciklama |
|---|---|
| `list_model_providers` | Tum model saglayicilarini listeler |
| `get_provider_models` | Bir saglayicinin modellerini listeler |
| `get_default_model` | Varsayilan modeli gosterir |
| `set_default_model` | Varsayilan modeli ayarlar |

### Tool Provider Yonetimi
| Arac | Aciklama |
|---|---|
| `list_tool_providers` | Tum tool saglayicilarini listeler |
| `list_builtin_tools` | Bir saglayicinin araclarini listeler |
| `list_workflow_tools` | Workflow-as-tool tanimlarini listeler |

### Ortam Degiskenleri
| Arac | Aciklama |
|---|---|
| `get_environment_variables` | Workflow env var'larini getirir |
| `get_conversation_variables` | Konusma degiskenlerini getirir |

### API Key Yonetimi
| Arac | Aciklama |
|---|---|
| `list_app_api_keys` | Uygulama API key'lerini listeler |
| `create_app_api_key` | Yeni API key olusturur |
| `delete_app_api_key` | API key'i siler |

### Etiketler
| Arac | Aciklama |
|---|---|
| `list_tags` | Tum etiketleri listeler |
| `create_tag` | Yeni etiket olusturur |

### Konusmalar & Mesajlar
| Arac | Aciklama |
|---|---|
| `list_conversations` | Chat konusmalarini listeler |
| `list_messages` | Mesajlari listeler |

### Erisim Kontrolu
| Arac | Aciklama |
|---|---|
| `toggle_app_site` | Web arayuzu erisimini ac/kapa |
| `toggle_app_api` | API erisimini ac/kapa |

### Ust Seviye Araclar
| Arac | Aciklama |
|---|---|
| `dsl_diff` | Iki YAML DSL'i karsilastirir, farklari gosterir |
| `batch_test` | Birden fazla test case'i toplu calistirir |
| `health_check` | Tum app'lerin durumunu ve hata oranlarini kontrol eder |
| `export_all_apps_dsl` | Tum uygulamalari YAML dosyalarina toplu export eder |

## Ortam Degiskenleri

| Degisken | Zorunlu | Varsayilan | Aciklama |
|---|---|---|---|
| `DIFY_BASE_URL` | Hayir | `http://localhost` | Dify instance URL'i |
| `DIFY_ADMIN_API_KEY` | Evet | - | Dify Admin API anahtari |
| `DIFY_WORKSPACE_ID` | Evet | - | Dify Workspace UUID'si |

## Mimari

```
Claude Code  <-->  MCP Server (stdio)  <-->  Dify Console API
                   (bu proje)                  (localhost/console/api)
                                                     |
                                                Dify Platform
                                              (Docker Compose)
```

MCP sunucusu, Dify Console API'sine `Authorization: Bearer <ADMIN_API_KEY>` + `X-WORKSPACE-ID` header'lari ile baglanir. Cookie/CSRF gerektirmez.

## Sorun Giderme

**"ADMIN_API_KEY env var not found"**
- `settings.json`'daki `env` blogunun dogru oldugunu kontrol et.

**"401 Unauthorized" / "Invalid token"**
- `docker-compose.yaml`'da `ADMIN_API_KEY` ve `ADMIN_API_KEY_ENABLE` satirlarinin `x-shared-env` altinda oldugundan emin ol.
- `docker compose down && docker compose up -d` ile yeniden baslat.
- Container icinde env'i kontrol et: `docker compose exec api env | grep ADMIN`

**"CSRF token is missing"**
- Admin API key dogru ayarlanmamis. Yukaridaki adimlari tekrar kontrol et.

## Lisans

MIT
