# Comandos Git para Inicializar y Subir a GitHub

## 1. Inicializar Git
```bash
git init
```

## 2. Agregar todos los archivos
```bash
git add .
```

## 3. Hacer commit inicial
```bash
git commit -m "Initial commit: BetMind AI - Motor Predictivo Cuantitativo"
```

## 4. Agregar Fase 4 (Motor Táctico y Narrativo)
```bash
git add .
git commit -m "feat: Fase 4 - Motor Táctico y Narrativo con Groq Llama 3.3

- Implementación completa del Cerebro Táctico con LLM
- Migración de Anthropic → Google Gemini → Groq (Llama 3.3)
- Control de concurrencia y reintentos para rate limits
- Integración con FastAPI mediante PredictionOrchestrator
- Persistencia en Supabase con modelo TacticalAnalysis
- Caché inteligente de 6 horas para reducir costos de API
- Ajuste de schemas Pydantic para Llama 3.3
- Migración SQL para tabla tactical_analyses
- Pruebas end-to-end exitosas (8/8 tests pasando)"
```

## 5. Crear repositorio en GitHub
Ve a https://github.com/new y crea un repositorio llamado `betmind-ai`

## 6. Agregar remoto y subir
```bash
git remote add origin https://github.com/TU_USUARIO/betmind-ai.git
git branch -M main
git push -u origin main
```

## Comandos Adicionales Útiles

### Ver estado
```bash
git status
```

### Ver historial de commits
```bash
git log --oneline
```

### Ver cambios sin commit
```bash
git diff
```

### Crear rama para nueva feature
```bash
git checkout -b feature/nombre-feature
```

### Hacer commit de cambios específicos
```bash
git add archivo.py
git commit -m "mensaje descriptivo"
```

### Subir cambios a rama existente
```bash
git push
```
