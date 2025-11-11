import http.server
import socketserver
import json
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import urllib.parse
import time
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configuração da Cloudinary
CLOUDINARY_CONFIG = {
    'cloud_name': 'dxgd62afy',
    'api_key': '965736457473817',
    'api_secret': 'm0JaTO4RGehmeZexoqjW6cGkLfs',
    'secure': True
}

# Inicializar Cloudinary
cloudinary.config(**CLOUDINARY_CONFIG)

# Configuração
PORT = 8000
DB_FILE = 'database.sqlite'

# Configuração do WhatsApp
WHATSAPP_CONFIG = {
    'api_url': 'https://api.whatsapp.com/send',
    'phone_number': '5519987790800',
    'default_message': 'Olá! Gostaria de mais informações sobre os produtos.'
}

# Configuração de E-mail (opcional)
EMAIL_CONFIG = {
    'enabled': False,
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email': 'seu-email@gmail.com',
    'password': 'sua-senha'
}


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Define o diretório base para servir arquivos estáticos
        self.base_directory = 'static'
        super().__init__(*args, directory=None, **kwargs)

    def translate_path(self, path):
        # Primeiro tenta servir da pasta static
        static_path = os.path.join(self.base_directory, path.lstrip('/'))
        if os.path.exists(static_path):
            return static_path

        # Se não encontrar, tenta servir da pasta templates para HTML
        if path.endswith('.html') or path == '/':
            template_path = os.path.join('templates', path.lstrip('/'))
            if os.path.exists(template_path):
                return template_path
            # Para a raiz, usa index.html
            if path == '/':
                return 'templates/index.html'

        # Fallback para o comportamento padrão
        return super().translate_path(path)

    def do_GET(self):
        print(f"📥 GET request: {self.path}")

        # API de produtos
        if self.path == '/api/produtos':
            self._handle_get_produtos()

        # API de saúde
        elif self.path == '/api/health':
            self._send_json_response(200, {
                'status': 'OK',
                'message': 'APPME Backend Python rodando!',
                'features': {
                    'whatsapp_integration': True,
                    'email_notifications': EMAIL_CONFIG['enabled'],
                    'database': 'SQLite',
                    'cloudinary_integration': True,
                    'products_count': get_products_count()
                }
            })

        # API para obter todos os pedidos
        elif self.path == '/api/pedidos':
            self._handle_get_pedidos()

        # API para gerar link do WhatsApp
        elif self.path.startswith('/api/whatsapp/'):
            self._handle_whatsapp_link()

        # ✅✅✅ CORREÇÃO: Rota específica para /admin ✅✅✅
        elif self.path == '/admin':
            filepath = 'templates/admin.html'
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Admin page not found")

        # Rota para favicon - EVITA ERRO 404
        elif self.path == '/favicon.ico':
            self._serve_favicon()

        # Rotas para ícones que estavam dando 404
        elif self.path in ['/flower', '/heart', '/box', '/star', '/coffee', '/zap',
                           '/award', '/feather', '/thermometer', '/circle', '/moon', '/wine']:
            self._serve_icon(self.path)

        # Servir páginas HTML da pasta templates
        elif self.path in ['/', '/index.html', '/produtos.html', '/admin.html',
                           '/cadastro.html', '/login.html', '/carrinho.html',
                           '/admin-pedidos.html', '/teste.html']:
            self._serve_html_page()

        # Servir arquivos estáticos (CSS, JS, imagens)
        else:
            self._serve_static_files()

    def _handle_get_produtos(self):
        """Manipula requisição GET para produtos"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM produtos ORDER BY created_at DESC")
            produtos_db = cursor.fetchall()
            conn.close()

            produtos = []
            for prod in produtos_db:
                produtos.append({
                    'id': prod[0],
                    'nome': prod[1],
                    'preco': prod[2],
                    'precoOriginal': prod[3],
                    'categoria': prod[4],
                    'descricao': prod[5],
                    'imagem_url': prod[6],
                    'imagem_public_id': prod[7],
                    'icone': prod[8],
                    'cor': prod[9],
                    'corGradiente': prod[10],
                    'desconto': prod[11],
                    'novo': bool(prod[12]),
                    'maisVendido': bool(prod[13])
                })

            self._send_json_response(200, produtos)
        except Exception as e:
            print(f"❌ Erro ao buscar produtos: {e}")
            self._send_json_response(
                500, {'error': f'Erro ao buscar produtos: {str(e)}'})

    def _handle_get_pedidos(self):
        """Manipula requisição GET para pedidos"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
            SELECT p.*, 
                   GROUP_CONCAT(ip.produto_nome || ' (Qtd: ' || ip.quantidade || ')') as itens_descricao
            FROM pedidos p
            LEFT JOIN itens_pedido ip ON p.id = ip.pedido_id
            GROUP BY p.id
            ORDER BY p.data_criacao DESC
            ''')
            pedidos_db = cursor.fetchall()
            conn.close()

            pedidos = []
            for pedido in pedidos_db:
                pedidos.append({
                    'id': pedido[0],
                    'cliente_nome': pedido[1],
                    'cliente_email': pedido[2],
                    'cliente_telefone': pedido[3],
                    'endereco_entrega': pedido[4],
                    'observacoes': pedido[5],
                    'total': pedido[6],
                    'status': pedido[7],
                    'data_criacao': pedido[8],
                    'itens_descricao': pedido[9] or 'Nenhum item'
                })

            self._send_json_response(200, pedidos)
        except Exception as e:
            self._send_json_response(500, {'error': str(e)})

    def _handle_whatsapp_link(self):
        """Manipula geração de link do WhatsApp"""
        try:
            pedido_id = self.path.split('/')[-1]
            whatsapp_link = self._gerar_link_whatsapp_vendedor(pedido_id)
            self._send_json_response(200, {'whatsapp_link': whatsapp_link})
        except Exception as e:
            self._send_json_response(500, {'error': str(e)})

    def _serve_favicon(self):
        """Serve o favicon.ico"""
        favicon_path = 'static/images/favicon.ico'
        if os.path.exists(favicon_path):
            self.send_response(200)
            self.send_header('Content-type', 'image/x-icon')
            self.end_headers()
            with open(favicon_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_icon(self, icon_name):
        """Serve ícones básicos (placeholder)"""
        self.send_response(200)
        self.send_header('Content-type', 'image/svg+xml')
        self.end_headers()

        # SVG simples como placeholder
        svg_placeholder = f'''
        <svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
            <rect width="100" height="100" fill="#f0f0f0" stroke="#ccc"/>
            <text x="50" y="50" text-anchor="middle" dy=".3em" fill="#666" font-family="Arial">
                {icon_name}
            </text>
        </svg>
        '''
        self.wfile.write(svg_placeholder.encode())

    def _serve_html_page(self):
        """Serve páginas HTML da pasta templates"""
        if self.path == '/':
            filepath = 'templates/index.html'
        else:
            filepath = f'templates{self.path}'

        if os.path.exists(filepath):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"File not found: {self.path}")

    def _serve_static_files(self):
        """Serve arquivos estáticos (CSS, JS, imagens)"""
        # Verifica se é um arquivo estático
        static_extensions = ('.css', '.js', '.png', '.jpg',
                             '.jpeg', '.gif', '.ico', '.svg')
        if any(self.path.endswith(ext) for ext in static_extensions):
            static_path = f'static{self.path}'
            if os.path.exists(static_path):
                self.send_response(200)
                if self.path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                elif self.path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                elif self.path.endswith('.png'):
                    self.send_header('Content-type', 'image/png')
                elif self.path.endswith('.jpg') or self.path.endswith('.jpeg'):
                    self.send_header('Content-type', 'image/jpeg')
                elif self.path.endswith('.gif'):
                    self.send_header('Content-type', 'image/gif')
                elif self.path.endswith('.svg'):
                    self.send_header('Content-type', 'image/svg+xml')
                self.end_headers()
                with open(static_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        # Se não encontrou, retorna 404
        self.send_error(404, f"File not found: {self.path}")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        print(f"📥 POST request: {self.path}")

        if self.path == '/api/pedidos':
            self._handle_post_pedidos(post_data)
        elif self.path == '/api/produtos':
            self._handle_post_produtos(post_data)
        elif self.path == '/api/upload-imagem':
            self._handle_upload_imagem(post_data)
        else:
            self._send_json_response(404, {'error': 'Endpoint não encontrado'})

    def _handle_post_pedidos(self, post_data):
        """Manipula POST para pedidos"""
        try:
            pedido_data = json.loads(post_data.decode())

            if not pedido_data.get('cliente') or not pedido_data['cliente'].get('nome'):
                raise ValueError("Dados do cliente são obrigatórios")

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO pedidos (cliente_nome, cliente_email, cliente_telefone, endereco_entrega, observacoes, total)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                pedido_data['cliente']['nome'],
                pedido_data['cliente']['email'],
                pedido_data['cliente']['telefone'],
                pedido_data['cliente']['endereco'],
                pedido_data['cliente']['observacoes'],
                pedido_data['total']
            ))

            pedido_id = cursor.lastrowid

            for item in pedido_data['itens']:
                cursor.execute('''
                INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, quantidade, preco_unitario)
                VALUES (?, ?, ?, ?, ?)
                ''', (
                    pedido_id,
                    item['id'],
                    item['nome'],
                    item['quantidade'],
                    item['preco']
                ))

            conn.commit()
            conn.close()

            whatsapp_link_vendedor = self._gerar_link_whatsapp_vendedor_detalhado(
                pedido_id, pedido_data)
            whatsapp_link_cliente = self._gerar_link_whatsapp_cliente(
                pedido_data)

            self._enviar_notificacao_pedido(pedido_id, pedido_data)

            if EMAIL_CONFIG['enabled']:
                try:
                    self._enviar_email_pedido(pedido_id, pedido_data)
                except Exception as e:
                    print(f"⚠️ Erro ao enviar e-mail: {e}")

            self._send_json_response(200, {
                'success': True,
                'message': 'Pedido criado com sucesso!',
                'pedido_id': pedido_id,
                'whatsapp_link_vendedor': whatsapp_link_vendedor,
                'whatsapp_link_cliente': whatsapp_link_cliente
            })

        except Exception as e:
            print(f"❌ Erro ao processar pedido: {e}")
            self._send_json_response(500, {'success': False, 'error': str(e)})

    def _handle_post_produtos(self, post_data):
        """Manipula POST para produtos"""
        try:
            produto_data = json.loads(post_data.decode())

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO produtos (nome, preco, preco_original, categoria, descricao, 
                                imagem_url, icone, cor, cor_gradiente, desconto, novo, mais_vendido)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                produto_data['nome'],
                produto_data['preco'],
                produto_data.get('preco_original'),
                produto_data['categoria'],
                produto_data['descricao'],
                produto_data.get('imagem_url'),
                produto_data.get('icone', 'box'),
                produto_data.get('cor', 'gray'),
                produto_data.get('cor_gradiente', 'from-gray-400 to-gray-600'),
                produto_data.get('desconto', 0),
                produto_data.get('novo', False),
                produto_data.get('mais_vendido', False)
            ))

            produto_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self._send_json_response(200, {
                'success': True,
                'produto_id': produto_id,
                'message': 'Produto cadastrado com sucesso'
            })

        except Exception as e:
            print(f"❌ Erro ao cadastrar produto: {e}")
            self._send_json_response(500, {'error': str(e)})

    def _handle_upload_imagem(self, post_data):
        """Manipula upload de imagem"""
        try:
            upload_data = json.loads(post_data.decode())
            result = self._upload_imagem_cloudinary(
                upload_data['imagem_base64'],
                upload_data['produto_id']
            )

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE produtos 
            SET imagem_url = ?, imagem_public_id = ?
            WHERE id = ?
            ''', (result['secure_url'], result['public_id'], upload_data['produto_id']))
            conn.commit()
            conn.close()

            self._send_json_response(200, {
                'success': True,
                'imagem_url': result['secure_url'],
                'public_id': result['public_id'],
                'message': 'Imagem enviada com sucesso!'
            })

        except Exception as e:
            print(f"❌ Erro no upload: {e}")
            self._send_json_response(500, {'error': str(e)})

    def _upload_imagem_cloudinary(self, imagem_base64, produto_id):
        """Faz upload da imagem para Cloudinary"""
        try:
            print("📤 Iniciando upload para Cloudinary...")
            result = cloudinary.uploader.upload(
                imagem_base64,
                folder="graca-presentes",
                public_id=f"produto_{produto_id}",
                overwrite=True,
                resource_type="image"
            )
            print(f"✅ Upload realizado! URL: {result['secure_url']}")
            return result
        except Exception as e:
            print(f"❌ Erro no upload: {e}")
            raise

    def _gerar_link_whatsapp_vendedor(self, pedido_id):
        """Gera link básico do WhatsApp para o vendedor"""
        mensagem = f"📦 Novo pedido #{pedido_id} recebido na Graça Presentes!"
        mensagem_encoded = urllib.parse.quote(mensagem)
        return f"https://api.whatsapp.com/send?phone={WHATSAPP_CONFIG['phone_number']}&text={mensagem_encoded}"

    def _gerar_link_whatsapp_vendedor_detalhado(self, pedido_id, pedido_data):
        """Gera link do WhatsApp para o vendedor com detalhes completos do pedido"""
        mensagem = self._formatar_mensagem_vendedor(pedido_id, pedido_data)
        mensagem_encoded = urllib.parse.quote(mensagem)
        return f"https://api.whatsapp.com/send?phone={WHATSAPP_CONFIG['phone_number']}&text={mensagem_encoded}"

    def _gerar_link_whatsapp_cliente(self, pedido_data):
        """Gera link do WhatsApp para o cliente confirmar pedido"""
        mensagem = f"Olá! Sou {pedido_data['cliente']['nome']}. Acabei de fazer um pedido na Graça Presentes (#{pedido_data.get('pedido_id', 'Novo')}) e gostaria de confirmar os detalhes."
        mensagem_encoded = urllib.parse.quote(mensagem)
        return f"https://api.whatsapp.com/send?phone={WHATSAPP_CONFIG['phone_number']}&text={mensagem_encoded}"

    def _formatar_mensagem_vendedor(self, pedido_id, pedido_data):
        """Formata a mensagem detalhada para o vendedor"""
        cliente = pedido_data['cliente']
        itens = pedido_data['itens']
        total = pedido_data['total']

        mensagem = "🎉 *NOVO PEDIDO - GRAÇA PRESENTES* 🎉\n\n"
        mensagem += f"*Pedido:* #{pedido_id}\n"
        mensagem += f"*Data:* {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

        mensagem += "*👤 DADOS DO CLIENTE:*\n"
        mensagem += f"• Nome: {cliente['nome']}\n"
        mensagem += f"• Email: {cliente['email']}\n"
        mensagem += f"• Telefone: {cliente['telefone']}\n"
        mensagem += f"• Endereço: {cliente['endereco']}\n"
        if cliente.get('observacoes'):
            mensagem += f"• Observações: {cliente['observacoes']}\n"
        mensagem += "\n"

        mensagem += "*🛍️ ITENS DO PEDIDO:*\n"
        for i, item in enumerate(itens, 1):
            subtotal = item['preco'] * item['quantidade']
            mensagem += f"{i}. {item['nome']}\n"
            mensagem += f"   Quantidade: {item['quantidade']}\n"
            mensagem += f"   Preço: R$ {item['preco']:.2f}\n"
            mensagem += f"   Subtotal: R$ {subtotal:.2f}\n\n"

        mensagem += f"*💰 TOTAL: R$ {total:.2f}*\n\n"
        mensagem += "📞 *Entre em contato com o cliente para confirmar o pedido!*"

        return mensagem

    def _enviar_notificacao_pedido(self, pedido_id, pedido_data):
        """Exibe notificação do pedido no console"""
        print("=" * 70)
        print("🎉 NOVO PEDIDO RECEBIDO - GRAÇA PRESENTES")
        print("=" * 70)
        print(f"📋 PEDIDO #: {pedido_id}")
        print(f"⏰ DATA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 70)
        print("👤 DADOS DO CLIENTE:")
        print(f"   Nome: {pedido_data['cliente']['nome']}")
        print(f"   Email: {pedido_data['cliente']['email']}")
        print(f"   Telefone: {pedido_data['cliente']['telefone']}")
        print(f"   Endereço: {pedido_data['cliente']['endereco']}")
        print(
            f"   Observações: {pedido_data['cliente'].get('observacoes', 'Nenhuma')}")
        print("=" * 70)
        print("🛍️ ITENS DO PEDIDO:")

        total = 0
        for i, item in enumerate(pedido_data['itens'], 1):
            subtotal = item['preco'] * item['quantidade']
            total += subtotal
            print(f"   {i}. {item['nome']}")
            print(f"      Quantidade: {item['quantidade']}")
            print(f"      Preço unitário: R$ {item['preco']:.2f}")
            print(f"      Subtotal: R$ {subtotal:.2f}")

        print("=" * 70)
        print(f"💰 TOTAL DO PEDIDO: R$ {total:.2f}")
        print("=" * 70)
        print("📱 LINK WHATSAPP GERADO - Entre em contato com o cliente!")
        print("=" * 70)

    def _enviar_email_pedido(self, pedido_id, pedido_data):
        """Envia e-mail de notificação do pedido"""
        if not EMAIL_CONFIG['enabled']:
            return

        try:
            server = smtplib.SMTP(
                EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])

            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = EMAIL_CONFIG['email']
            msg['Subject'] = f'🎉 Novo Pedido #{pedido_id} - Graça Presentes'

            body = self._formatar_mensagem_vendedor(pedido_id, pedido_data)
            msg.attach(MIMEText(body, 'plain'))

            server.send_message(msg)
            server.quit()

            print("✅ E-mail de notificação enviado com sucesso!")

        except Exception as e:
            print(f"❌ Erro ao enviar e-mail: {e}")
            raise

    def _send_json_response(self, status_code, data):
        """Envia resposta JSON"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Manipula requisições OPTIONS para CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def create_tables(cursor):
    """Cria as tabelas do banco de dados"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        preco REAL NOT NULL,
        preco_original REAL,
        categoria TEXT NOT NULL,
        descricao TEXT,
        imagem_url TEXT,
        imagem_public_id TEXT,
        icone TEXT,
        cor TEXT,
        cor_gradiente TEXT,
        desconto INTEGER,
        novo BOOLEAN,
        mais_vendido BOOLEAN,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_nome TEXT NOT NULL,
        cliente_email TEXT NOT NULL,
        cliente_telefone TEXT,
        endereco_entrega TEXT NOT NULL,
        observacoes TEXT,
        total REAL NOT NULL,
        status TEXT DEFAULT 'recebido',
        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER,
        produto_id INTEGER,
        produto_nome TEXT,
        quantidade INTEGER,
        preco_unitario REAL,
        FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
    )
    ''')


def insert_sample_data(cursor):
    """Insere dados de exemplo no banco"""
    produtos = [
        (1, "Buquê de Rosas", 89.90, 99.90, "Flores", "Buquê com 12 rosas vermelhas frescas",
         None, None, "flower", "pink", "from-pink-400 to-pink-600", 10, 1, 0),
        (2, "Caixa de Chocolates", 59.90, None, "Doces", "16 chocolates finos selecionados",
         None, None, "box", "yellow", "from-yellow-400 to-yellow-600", 0, 0, 1),
        (3, "Urso de Pelúcia", 69.90, 87.90, "Pelúcias", "Urso marrom 40cm super fofo",
         None, None, "heart", "blue", "from-blue-400 to-blue-600", 20, 0, 0),
        (4, "Kit Beleza", 129.90, None, "Cosméticos", "Kit com 5 produtos de beleza premium",
         None, None, "star", "purple", "from-purple-400 to-purple-600", 0, 1, 0),
        (5, "Cesta Gourmet", 99.90, None, "Kits", "Café especial e biscoitos finos",
         None, None, "coffee", "brown", "from-yellow-600 to-brown-600", 0, 0, 1),
        (6, "Vela Aromática", 39.90, None, "Decoração", "Vela de soja com aroma de lavanda",
         None, None, "zap", "pink", "from-pink-300 to-pink-500", 0, 0, 0),
        (7, "Colar de Prata", 149.90, None, "Joias", "Colar com pingente de coração",
         None, None, "award", "gray", "from-gray-400 to-gray-600", 0, 1, 0),
        (8, "Planta Suculenta", 49.90, None, "Decoração", "Kit com 3 plantas suculentas",
         None, None, "feather", "green", "from-green-400 to-green-600", 0, 0, 0),
        (9, "Kit Chá Premium", 79.90, None, "Kits", "Seleção de chás especiais importados",
         None, None, "thermometer", "green", "from-green-300 to-green-500", 0, 1, 0),
        (10, "Pote de Biscoitos", 45.90, None, "Doces", "Biscoitos artesanais com chocolate",
         None, None, "circle", "yellow", "from-yellow-300 to-yellow-500", 0, 0, 0),
        (11, "Kit Relaxamento", 119.90, None, "Cosméticos", "Velas, óleos e sais aromáticos",
         None, None, "moon", "purple", "from-purple-300 to-purple-500", 0, 0, 1),
        (12, "Cesta Vinho", 159.90, None, "Kits", "Vinho tinto e queijos selecionados",
         None, None, "wine", "red", "from-red-400 to-red-600", 0, 0, 0)
    ]

    cursor.executemany('''
    INSERT INTO produtos (id, nome, preco, preco_original, categoria, descricao, imagem_url, imagem_public_id, icone, cor, cor_gradiente, desconto, novo, mais_vendido)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', produtos)
    print("✅ Produtos iniciais inseridos no banco")


def init_db():
    """Inicializa o banco de dados"""
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='produtos'")
            tabela_existe = cursor.fetchone()

            if not tabela_existe:
                print("🔄 Criando tabelas do banco...")
                create_tables(cursor)
                insert_sample_data(cursor)
            else:
                cursor.execute("PRAGMA table_info(produtos)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'imagem_url' not in columns:
                    print("🔄 Adicionando colunas de imagem...")
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS produtos_temp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        preco REAL NOT NULL,
                        preco_original REAL,
                        categoria TEXT NOT NULL,
                        descricao TEXT,
                        imagem_url TEXT,
                        imagem_public_id TEXT,
                        icone TEXT,
                        cor TEXT,
                        cor_gradiente TEXT,
                        desconto INTEGER,
                        novo BOOLEAN,
                        mais_vendido BOOLEAN,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    ''')

                    cursor.execute(
                        "SELECT id, nome, preco, preco_original, categoria, descricao, icone, cor, cor_gradiente, desconto, novo, mais_vendido FROM produtos")
                    old_data = cursor.fetchall()

                    for row in old_data:
                        cursor.execute('''
                        INSERT INTO produtos_temp (id, nome, preco, preco_original, categoria, descricao, imagem_url, imagem_public_id, icone, cor, cor_gradiente, desconto, novo, mais_vendido)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', row + (None, None))

                    cursor.execute("DROP TABLE produtos")
                    cursor.execute(
                        "ALTER TABLE produtos_temp RENAME TO produtos")

            conn.commit()
            conn.close()
            print("✅ Banco de dados inicializado com sucesso")
            return

        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                print(
                    f"🔄 Banco está bloqueado, tentando novamente em {retry_delay} segundos...")
                time.sleep(retry_delay)
                continue
            else:
                print(f"❌ Erro ao inicializar banco: {e}")
                return
        except Exception as e:
            print(f"❌ Erro ao inicializar banco: {e}")
            return


def get_products_count():
    """Retorna o número total de produtos cadastrados"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM produtos")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


# Inicializar banco
init_db()

print("🚀 GRAÇA PRESENTES - Servidor Python Iniciado!")
print("📍 URL: http://localhost:8000")
print("🔧 API: http://localhost:8000/api/produtos")
print("👨‍💼 Admin: http://localhost:8000/admin")
print("❤️  Saúde: http://localhost:8000/api/health")
print("📱 WhatsApp Integrado")
print("📧 E-mail: " +
      ("✅ Ativado" if EMAIL_CONFIG['enabled'] else "❌ Desativado"))
print("☁️  Cloudinary: ✅ Integrado")
print("💾 Banco de dados: SQLite")
print("📊 Produtos cadastrados:", get_products_count())
print("⏹️  Para parar: Ctrl+C")
print("=" * 60)

try:
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"✅ Servidor rodando na porta {PORT}")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n🛑 Servidor parado com sucesso!")
except Exception as e:
    print(f"\n❌ Erro no servidor: {e}")
