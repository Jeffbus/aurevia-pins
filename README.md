# Aurevia Pin Maker — Deploy en Railway

## Qué hace
Recibe un CSV con los datos de tus pines (hook, body, cta, drive_url)
y devuelve un ZIP con las imágenes procesadas con texto superpuesto.

## Plantillas incluidas
- **money_post** — Hook grande arriba, body en medio, botón CTA coral abajo
- **informative** — Hook arriba, body en caja semitransparente, CTA discreto
- **retention** — Estilo emocional, hook centrado, cuerpo secundario, CTA limpio

---

## Pasos para subir a Railway

### 1. Crea cuenta en Railway
Ve a https://railway.app y regístrate con GitHub.

### 2. Sube el código a GitHub
Crea un repositorio nuevo en GitHub llamado `aurevia-pins`.
Sube estos archivos:
- main.py
- requirements.txt
- Dockerfile

### 3. Deploy desde Railway
1. En Railway → New Project → Deploy from GitHub repo
2. Selecciona `aurevia-pins`
3. Railway detecta el Dockerfile automáticamente
4. Espera ~2 minutos que construya
5. Ve a Settings → Networking → Generate Domain
6. Copia tu URL pública (ej: https://aurevia-pins.up.railway.app)

### 4. Verifica que funciona
Abre en el browser: `https://TU-URL.up.railway.app/health`
Debe responder: `{"status":"ok"}`

---

## Cómo usar

### Opción A — Interfaz web
1. Abre `https://TU-URL.up.railway.app/`
2. Sube tu CSV
3. Haz clic en "Generar Pines"
4. Descarga el ZIP con los pines listos

### Opción B — Desde n8n
Agrega un nodo HTTP Request en n8n:
- Method: POST
- URL: https://TU-URL.up.railway.app/process
- Body: multipart/form-data
  - csv_file: tu CSV

---

## Formato del CSV

```
filename,content_type,hook,body_text,cta,template,drive_url,article_url,product_url
pin_001.jpg,money_post,"TIRED ALL DAY?","Support your energy naturally","Learn More",auto,https://drive.google.com/file/d/XXXX/view,...,...
```

### Columnas importantes
| Columna | Descripción |
|---------|-------------|
| filename | Nombre del archivo de salida |
| content_type | money_post / informative / retention |
| hook | Texto grande (máx 6-8 palabras) |
| body_text | Texto secundario (máx 10 palabras) |
| cta | Botón call-to-action (máx 3 palabras) |
| template | auto (recomendado) o nombre específico |
| drive_url | URL de la imagen base en Google Drive |

### drive_url — formatos aceptados
- `https://drive.google.com/file/d/FILE_ID/view`
- `https://drive.google.com/uc?id=FILE_ID`
- Cualquier URL pública de imagen (JPG, PNG)

---

## Costos Railway
Plan gratuito: $5 de crédito gratis por mes — suficiente para pruebas.
Para uso continuo: ~$5/mes en el plan Hobby.
