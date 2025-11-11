// Sistema de Carrinho ATUALIZADO para Python
class Carrinho {
    constructor() {
        this.itens = JSON.parse(localStorage.getItem('carrinho')) || [];
        this.desconto = 0;
        this.atualizarContador();
    }

    adicionarItem(produto) {
        const itemExistente = this.itens.find(item => item.id === produto.id);
        
        if (itemExistente) {
            itemExistente.quantidade += 1;
        } else {
            this.itens.push({
                ...produto,
                quantidade: 1
            });
        }
        
        this.salvar();
        this.atualizarContador();
        this.mostrarFeedback();
    }

    removerItem(id) {
        this.itens = this.itens.filter(item => item.id !== id);
        this.salvar();
        this.atualizarContador();
    }

    atualizarQuantidade(id, quantidade) {
        const item = this.itens.find(item => item.id === id);
        if (item) {
            item.quantidade = quantidade;
            if (item.quantidade <= 0) {
                this.removerItem(id);
            } else {
                this.salvar();
            }
        }
        this.atualizarContador();
    }

    atualizarContador() {
        const contadores = document.querySelectorAll('#cart-count');
        const totalItens = this.itens.reduce((total, item) => total + item.quantidade, 0);
        
        contadores.forEach(contador => {
            contador.textContent = totalItens;
        });
    }

    mostrarFeedback() {
        const feedback = document.createElement('div');
        feedback.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-bounce';
        feedback.innerHTML = `
            <div class="flex items-center">
                <i data-feather="check-circle" class="w-5 h-5 mr-2"></i>
                <span>Produto adicionado ao carrinho!</span>
            </div>
        `;
        
        document.body.appendChild(feedback);
        feather.replace();
        
        setTimeout(() => {
            feedback.remove();
        }, 3000);
    }

    getTotal() {
        return this.itens.reduce((total, item) => total + (item.preco * item.quantidade), 0);
    }

    salvar() {
        localStorage.setItem('carrinho', JSON.stringify(this.itens));
    }

    limpar() {
        this.itens = [];
        this.desconto = 0;
        this.salvar();
        this.atualizarContador();
    }

    // NOVO MÉTODO: Enviar pedido para o backend Python
    async enviarPedido(dadosCliente) {
        try {
            const pedidoData = {
                cliente: {
                    nome: dadosCliente.nome,
                    email: dadosCliente.email,
                    telefone: dadosCliente.telefone,
                    endereco: dadosCliente.endereco,
                    observacoes: dadosCliente.observacoes
                },
                itens: this.itens,
                total: this.getTotal() + 15 - (this.desconto || 0) // Inclui frete e desconto
            };

            console.log('Enviando pedido:', pedidoData);

            const response = await fetch('/api/pedidos', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pedidoData)
            });

            const result = await response.json();
            
            if (result.success) {
                return { 
                    success: true, 
                    pedido_id: result.pedido_id,
                    message: result.message
                };
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('Erro ao enviar pedido:', error);
            return { 
                success: false, 
                error: 'Erro ao conectar com o servidor. Verifique se o servidor Python está rodando.' 
            };
        }
    }
}

// Inicializar carrinho
const carrinho = new Carrinho();

// Função global para atualizar contador
function atualizarContadorCarrinho() {
    carrinho.atualizarContador();
}