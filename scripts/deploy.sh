#!/usr/bin/env bash
# ==============================================================================
# Script de Despliegue Automatizado para FX-Pulse / Currency-Radar
# ==============================================================================

set -e

REPO_NAME="fx-pulse"
COMMIT_MSG="feat: initial FX analysis dashboard – all major & exotic pairs"

echo "=========================================================="
echo " 🚀 INICIANDO DESPLIEGUE EN GITHUB: $REPO_NAME"
echo "=========================================================="

# 1. Asegurar que estamos en el directorio raíz del proyecto
cd "$(dirname "$0")/.."

# 2. Inicializar repositorio git si no existe
if [ ! -d ".git" ]; then
    echo "📦 Inicializando repositorio Git local..."
    git init
    git branch -M main
else
    echo "ℹ️ Repositorio Git ya inicializado."
fi

# 3. Añadir todos los archivos y realizar commit
echo "📝 Añadiendo archivos al commit..."
git add .
git commit -m "$COMMIT_MSG" || echo "ℹ️ Nada nuevo por commitear."

# 4. Crear o sincronizar repositorio en GitHub
if command -v gh &> /dev/null; then
    echo "🤖 GitHub CLI detectado (gh). Verificando autenticación y creando repo..."
    if ! gh auth status &> /dev/null; then
        echo "⚠️ gh no está autenticado. Por favor ejecuta 'gh auth login' primero."
        exit 1
    fi

    # Verificar si el repo remoto ya existe
    if gh repo view "$REPO_NAME" &> /dev/null; then
        echo "ℹ️ El repositorio $REPO_NAME ya existe en GitHub. Haciendo push..."
        git push -u origin main
    else
        echo "✨ Creando repositorio público en GitHub con gh..."
        gh repo create "$REPO_NAME" --public --source=. --push
    fi
else
    echo "⚠️ 'gh' CLI no está instalado o en el PATH."
    echo "Pasos manuales para completar el despliegue:"
    echo "  1. Crea un repo público en https://github.com/new llamado '$REPO_NAME'"
    echo "  2. Ejecuta:"
    echo "       git remote add origin https://github.com/<TU_USUARIO>/$REPO_NAME.git"
    echo "       git push -u origin main"
    exit 0
fi

# 5. Confirmación final
echo "=========================================================="
echo "✅ Push completado con éxito."
echo "Último commit:"
git log --oneline -1
echo "----------------------------------------------------------"
REPO_URL=$(gh repo view --json url -q ".url" 2>/dev/null || echo "https://github.com/<tu_usuario>/$REPO_NAME")
echo "🌐 URL Final del Repositorio: $REPO_URL"
echo "=========================================================="
