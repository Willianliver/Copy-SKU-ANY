# 🧬 Copy SKU ANY — Automação de Clonagem de Produtos AnyMarket

Este repositório contém scripts Python desenvolvidos para automatizar a **duplicação e clonagem de produtos (SKUs)** na plataforma **AnyMarket**.
Os scripts utilizam a **API AnyMarket** para buscar dados de produtos existentes e criar novos produtos com novos SKUs e EANs, mantendo imagens, categorias e estrutura original.

---

## 📁 Estrutura do Repositório

```
COPY SIMPLE P KIT/        → Pasta auxiliar com arquivos adicionais
.gitignore                → Arquivo padrão do Git
ANY1xANY2.py              → Script de clonagem simples (API entre contas 1 e 2)
ANY1xREPLETA.py           → Script de clonagem simples (conta 1 → Repleta)
Variations ANY1xANY2.py   → Clonagem de produtos com variações (contas 1 e 2)
Variations ANY1xREPLETA.py→ Clonagem de produtos com variações (conta 1 → Repleta)
main.py                   → Script principal (executa conforme seleção do usuário)
variations.py             → Lógica auxiliar para produtos com variações
```

---

## ⚙️ Funcionamento

### 🔹 Clonagem simples (`ANY1xANY2.py` e `ANY1xREPLETA.py`)

Esses scripts são usados para duplicar **produtos simples (sem variações)**.Eles:

1. Solicitam o **ID do produto original (id_prod_hub)**.
2. Buscam os dados do produto via **API GET**.
3. Removem campos que causariam erro (ex: `id`, `idVariation`, etc.).
4. Solicitam **novo SKU** e **novo EAN**.
5. Criam o novo produto via **POST** na API.

### 🔹 Clonagem com variações (`Variations ANY1xANY2.py` e `Variations ANY1xREPLETA.py`)

Usados para produtos com **variações (cores, tamanhos, etc.)**.Eles:

1. Identificam o produto pai e suas variações (SKUs filhos).
2. Solicitam **novos SKUs e EANs** para cada variação.
3. Mantêm imagens, categorias e descrições originais.
4. Fazem o POST mantendo `hasVariations=True` e a hierarquia correta.

### 🔹 Script principal (`main.py`)

Centraliza a execução — permite escolher qual operação rodar, simplificando o uso.

### 🔹 Módulo auxiliar (`variations.py`)

Contém funções reutilizáveis que lidam com o tratamento de produtos com variações.

---

## 🧩 Requisitos

- Python 3.8+
- Biblioteca `requests` instalada

Instalação:

```bash
pip install requests
```

---

## 🔑 Autenticação

Os scripts utilizam o token da API AnyMarket no header da requisição:

```python
headers = {
    "Content-Type": "application/json",
    "gumgaToken": "SEU_TOKEN_AQUI"
}
```

---

## 🌎 Idiomas

Este repositório é bilíngue.
Abaixo, segue a versão em inglês.

---

# 🧬 Copy SKU ANY — AnyMarket Product Clone Automation

This repository contains Python scripts designed to **automate product (SKU) duplication** in the **AnyMarket** platform.
The scripts use the **AnyMarket API** to fetch product data and create new ones with updated SKUs and EANs, preserving images, categories, and structure.

---

## 📁 Repository Structure

```
COPY SIMPLE P KIT/        → Helper folder
.gitignore                → Git ignore file
ANY1xANY2.py              → Simple clone script (API 1 ↔ 2)
ANY1xREPLETA.py           → Simple clone script (API 1 → Repleta)
Variations ANY1xANY2.py   → Clone script for variation products (1 ↔ 2)
Variations ANY1xREPLETA.py→ Clone script for variation products (1 → Repleta)
main.py                   → Main controller script
variations.py             → Helper for variation logic
```

---

## ⚙️ How It Works

### 🔹 Simple Clone (`ANY1xANY2.py` and `ANY1xREPLETA.py`)

For **non-variable products**.Steps:

1. Ask for **original product ID (id_prod_hub)**.
2. Fetch product data via **GET** request.
3. Remove unwanted fields (`id`, `idVariation`, etc.).
4. Ask for **new SKU** and **new EAN**.
5. Create the new product via **POST** request.

### 🔹 Variation Clone (`Variations ANY1xANY2.py` and `Variations ANY1xREPLETA.py`)

For **products with variations (e.g., color, size)**.Steps:

1. Identify parent product and its variations.
2. Request **new SKUs and EANs** for each variation.
3. Keep original images, categories, and description.
4. Post new product with `hasVariations=True`.

### 🔹 Main Script (`main.py`)

Centralizes execution — lets you select which operation to run.

### 🔹 Variation Module (`variations.py`)

Reusable functions to handle variation-based logic.

---

## 🧩 Requirements

- Python 3.8+
- `requests` library

Install:

```bash
pip install requests
```

---

## 🔑 Authentication

API token must be set in the request headers:

```python
headers = {
    "Content-Type": "application/json",
    "gumgaToken": "YOUR_TOKEN_HERE"
}
```

---

## 👨‍💻 Author

Developed by **Willian Pires**
For automation and API integration with AnyMarket.
