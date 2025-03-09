import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import os
import sys
import time
from web3 import Web3
import requests
import pandas as pd
from datetime import datetime
import webbrowser
# 导入自定义工具函数
from wallet_utils import get_wallet_balances, get_transaction_count, get_contract_interactions, get_token_info

class MonadWalletTool:
    """Monad测试币钱包工具主类"""
    
    def __init__(self, root):
        """初始化应用"""
        self.root = root
        self.root.title("Monad钱包查询工具")  # 窗口标题栏
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)
        
        # 变量初始化
        self.rpc_url = tk.StringVar(value="https://testnet-rpc.monad.xyz/")
        self.wallet_address = tk.StringVar()  # 钱包地址输入变量
        self.web3 = None
        self.wallets = []  # 钱包地址列表
        self.contracts = {}  # 合约地址和ABI {address: abi}
        
        # 数据文件路径 - 修改为使用更可靠的路径
        # 方法1: 使用exe所在目录
        try:
            # 判断是否在PyInstaller环境中
            if getattr(sys, 'frozen', False):
                # 如果是打包后的环境，使用exe所在目录
                base_path = os.path.dirname(sys.executable)
            else:
                # 如果是开发环境，使用脚本所在目录
                base_path = os.path.dirname(os.path.abspath(__file__))
                
            self.data_dir = os.path.join(base_path, "data")
        except:
            # 方法2: 备用方案，使用用户文档目录
            user_docs = os.path.join(os.path.expanduser('~'), 'Documents', 'MonadWalletTool')
            self.data_dir = user_docs
            
        self.wallets_file = os.path.join(self.data_dir, "wallets.json")
        
        # 确保数据目录存在
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 记录数据保存位置到日志
        print(f"数据将保存到: {self.data_dir}")
        
        # 进度指示器控制
        self.progress_running = False
        self.progress_thread = None
        
        # 创建UI
        self.create_ui()
        
        # 自动连接到默认RPC节点
        self.connect_to_rpc()
        
        # 加载保存的钱包地址
        self.load_wallets()
        
    def create_ui(self):
        """创建用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=0)  # 移除内边距，最大化利用空间
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置根窗口网格
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # 配置主框架网格
        main_frame.columnconfigure(0, weight=1)  # 整个区域
        main_frame.rowconfigure(0, weight=0)  # 作者信息区域
        main_frame.rowconfigure(1, weight=0)  # RPC区域
        main_frame.rowconfigure(2, weight=0)  # 钱包输入区域
        main_frame.rowconfigure(3, weight=0)  # 操作按钮区域
        main_frame.rowconfigure(4, weight=3)  # 结果表格区域
        main_frame.rowconfigure(5, weight=1)  # 日志区域
        
        # ==== 0. 顶部作者信息 ====
        top_bar = ttk.Frame(main_frame, style="TopBar.TFrame", padding=(0, 0, 5, 0))
        top_bar.grid(row=0, column=0, sticky="ew")
        
        # 创建右侧对齐的作者信息框架
        author_frame = ttk.Frame(top_bar)
        author_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # 提示文本
        ttk.Label(author_frame, text="点击访问作者Twitter").pack(side=tk.LEFT, padx=5)
        
        # 创建可点击的链接
        author_label = ttk.Label(
            author_frame, 
            text="by 0x1c3", 
            foreground="blue", 
            cursor="hand2",
            font=("Arial", 10, "underline")
        )
        author_label.pack(side=tk.LEFT)
        author_label.bind("<Button-1>", lambda e: webbrowser.open_new("https://x.com/0x1c3win"))
        
        # 添加分隔线
        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.grid(row=0, column=0, sticky="ew", pady=(25, 0))
        
        # 内容区域容器，添加内边距
        content_frame = ttk.Frame(main_frame, padding=10)
        content_frame.grid(row=1, column=0, rowspan=5, sticky="nsew")
        
        # 配置内容框架网格
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=0)  # RPC区域
        content_frame.rowconfigure(1, weight=0)  # 钱包输入区域
        content_frame.rowconfigure(2, weight=0)  # 操作按钮区域
        content_frame.rowconfigure(3, weight=3)  # 结果表格区域
        content_frame.rowconfigure(4, weight=1)  # 日志区域
        
        # ==== 1. RPC输入框 + 测试连接按钮 ====
        rpc_frame = ttk.LabelFrame(content_frame, text="RPC配置", padding=10)
        rpc_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Label(rpc_frame, text="RPC URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(rpc_frame, textvariable=self.rpc_url, width=50).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(rpc_frame, text="测试连接", command=self.test_rpc_connection).grid(row=0, column=2, padx=5, pady=5)
        
        rpc_frame.columnconfigure(1, weight=1)
        
        # ==== 2. 钱包地址输入区域 ====
        wallet_frame = ttk.LabelFrame(content_frame, text="钱包地址", padding=10)
        wallet_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Label(wallet_frame, text="输入钱包地址:").grid(row=0, column=0, sticky="nw", padx=5, pady=5)
        
        # 使用多行文本输入框替代单行输入框
        self.wallet_text = scrolledtext.ScrolledText(wallet_frame, wrap=tk.WORD, height=6, width=70)
        self.wallet_text.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(wallet_frame, text="添加到列表", command=self.add_wallet).grid(row=0, column=2, padx=5, pady=5, sticky="n")
        
        ttk.Label(wallet_frame, text="提示: 每行输入一个钱包地址").grid(row=1, column=1, sticky="w", padx=5)
        
        wallet_frame.columnconfigure(1, weight=1)
        
        # ==== 3. 操作按钮区域 ====
        btn_frame = ttk.Frame(content_frame, padding=10)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        # 将原来的两个查询按钮替换为一个一键查询按钮
        ttk.Button(btn_frame, text="一键查询", command=self.query_all).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_wallets).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="导出结果", command=self.export_results).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="清除日志", command=self.clear_log).pack(side=tk.LEFT, padx=10)
        
        # ==== 4. 结果表格区域 ====
        result_frame = ttk.LabelFrame(content_frame, text="查询结果", padding=10)
        result_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        
        # 创建带滚动条的表格
        table_frame = ttk.Frame(result_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格 - 添加序号列
        columns = ('index', 'address', 'balance', 'transactions')
        self.result_table = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        # 定义列
        self.result_table.heading('index', text='序号')
        self.result_table.heading('address', text='钱包地址')
        self.result_table.heading('balance', text='余额 (MON)')
        self.result_table.heading('transactions', text='交易数')
        
        # 设置列宽
        self.result_table.column('index', width=50, anchor='center')
        self.result_table.column('address', width=400, anchor='w')
        self.result_table.column('balance', width=150, anchor='center')
        self.result_table.column('transactions', width=150, anchor='center')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.result_table.yview)
        self.result_table.configure(yscrollcommand=scrollbar.set)
        
        # 放置表格和滚动条
        self.result_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ==== 5. 日志显示区域 ====
        log_frame = ttk.LabelFrame(content_frame, text="日志", padding=10)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
    
    def log(self, message):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def start_progress_indicator(self, message="正在查询"):
        """启动进度指示器，显示动态的省略号"""
        # 如果已经有一个进度指示器在运行，先停止它
        self.stop_progress_indicator()
        
        # 设置标志为运行状态
        self.progress_running = True
        
        # 启动线程更新进度指示器
        def update_progress():
            dot_count = 0
            base_message = message
            
            while self.progress_running:
                # 创建省略号字符串
                dots = "." * dot_count
                full_message = f"{base_message}{dots}"
                
                # 更新日志
                self.log_text.config(state=tk.NORMAL)
                
                # 寻找最后一行并检查是否是进度指示器
                last_line_start = self.log_text.index("end-1c linestart")
                last_line = self.log_text.get(last_line_start, "end-1c")
                
                if last_line.startswith(f"[{datetime.now().strftime('%H:%M:%S')}] {base_message}"):
                    # 如果最后一行是进度指示器，替换它
                    self.log_text.delete(last_line_start, "end-1c")
                    self.log_text.insert("end-1c", f"[{datetime.now().strftime('%H:%M:%S')}] {full_message}")
                else:
                    # 否则添加新行
                    self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {full_message}\n")
                
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
                
                # 增加点数，循环显示1-5个点
                dot_count = (dot_count + 1) % 6
                if dot_count == 0:
                    dot_count = 1
                    
                # 暂停一段时间
                time.sleep(0.5)
        
        # 启动更新线程
        self.progress_thread = threading.Thread(target=update_progress)
        self.progress_thread.daemon = True
        self.progress_thread.start()
    
    def stop_progress_indicator(self):
        """停止进度指示器"""
        if self.progress_running:
            self.progress_running = False
            # 等待线程结束
            if self.progress_thread and self.progress_thread.is_alive():
                self.progress_thread.join(1.0)  # 等待最多1秒
            
            self.progress_thread = None
    
    def connect_to_rpc(self):
        """连接到RPC节点"""
        url = self.rpc_url.get()
        
        try:
            # 创建Web3连接
            self.web3 = Web3(Web3.HTTPProvider(url))
            
            # 测试连接
            if self.web3.is_connected():
                block_number = self.web3.eth.block_number
                self.log(f"已自动连接到 {url}, 当前区块: {block_number}")
                return True
            else:
                self.log(f"自动连接到 {url} 失败")
                self.web3 = None
                return False
        except Exception as e:
            self.log(f"连接错误: {str(e)}")
            self.web3 = None
            return False
    
    def test_rpc_connection(self):
        """测试RPC连接 - 用户手动测试"""
        url = self.rpc_url.get()
        self.log(f"测试连接到 {url}...")
        
        try:
            # 创建Web3连接
            self.web3 = Web3(Web3.HTTPProvider(url))
            
            # 测试连接
            if self.web3.is_connected():
                block_number = self.web3.eth.block_number
                self.log(f"连接成功! 当前区块: {block_number}")
                return True
            else:
                self.log("连接失败: Web3无法连接到RPC节点")
                self.web3 = None
                return False
        except Exception as e:
            self.log(f"连接错误: {str(e)}")
            self.web3 = None
            return False
    
    def ensure_connection(self):
        """确保已连接到RPC节点，如果未连接则尝试连接"""
        if self.web3 and self.web3.is_connected():
            return True
        else:
            self.log("未检测到有效连接，尝试连接到RPC节点...")
            return self.connect_to_rpc()
    
    def add_wallet(self):
        """添加钱包地址到列表"""
        addresses_text = self.wallet_text.get("1.0", tk.END).strip()
        
        if not addresses_text:
            messagebox.showinfo("提示", "请输入钱包地址")
            return
            
        # 按行分割地址
        addresses = [addr.strip() for addr in addresses_text.split('\n') if addr.strip()]
        
        # 确保已连接到RPC
        self.ensure_connection()
        
        # 验证并添加地址
        valid_addresses = []
        invalid_addresses = []
        
        for addr in addresses:
            if self.web3 and self.web3.is_address(addr):
                valid_addresses.append(self.web3.to_checksum_address(addr))
            elif addr.startswith('0x') and len(addr) == 42:
                valid_addresses.append(addr)
            else:
                invalid_addresses.append(addr)
        
        # 添加有效地址到列表
        added_count = 0
        for addr in valid_addresses:
            if addr not in self.wallets:
                self.wallets.append(addr)
                added_count += 1
        
        # 清空输入框
        self.wallet_text.delete("1.0", tk.END)
        
        # 显示导入结果
        result_msg = f"已添加 {added_count} 个钱包地址到列表"
        if len(invalid_addresses) > 0:
            result_msg += f"\n有 {len(invalid_addresses)} 个无效地址被忽略"
        
        self.log(result_msg)
        
        # 如果有无效地址，显示详细信息
        if invalid_addresses:
            detail_msg = "无效地址: " + ", ".join(invalid_addresses)
            self.log(detail_msg)
        
        # 更新表格
        self.update_result_table()
        
        # 保存钱包列表到文件
        self.save_wallets()
    
    def clear_wallets(self):
        """清空钱包列表"""
        if not self.wallets:
            return
        
        if messagebox.askyesno("确认", "确定要清空钱包列表吗?"):
            self.wallets = []
            # 清空表格
            for item in self.result_table.get_children():
                self.result_table.delete(item)
            self.log("已清空钱包列表")
            
            # 保存空列表到文件
            self.save_wallets()
    
    def update_result_table(self):
        """更新结果表格"""
        # 清空表格
        for item in self.result_table.get_children():
            self.result_table.delete(item)
        
        # 添加钱包地址到表格（带序号）
        for idx, addr in enumerate(self.wallets, 1):
            self.result_table.insert('', tk.END, values=(idx, addr, '-', '-'))
    
    def query_all(self):
        """一键查询钱包的余额和交易数量"""
        # 确保已连接到RPC
        if not self.ensure_connection():
            self.log("无法连接到RPC节点，请检查网络连接或RPC URL")
            return
            
        if not self.wallets:
            # 如果钱包列表为空，尝试从输入框获取地址并添加
            self.add_wallet()
            if not self.wallets:
                self.log("没有钱包地址可查询")
                return
        
        # 启动进度指示器
        msg = f"正在查询 {len(self.wallets)} 个钱包的余额和交易数"
        self.start_progress_indicator(msg)
        
        def query_task():
            try:
                # 使用工具函数同时查询余额和交易数量
                balance_results = get_wallet_balances(self.web3, self.wallets)
                tx_results = get_transaction_count(self.web3, self.wallets)
                
                # 停止进度指示器
                self.stop_progress_indicator()
                
                # 更新表格
                for idx, addr in enumerate(self.wallets, 1):
                    # 查找表格中对应的行
                    for item in self.result_table.get_children():
                        item_values = self.result_table.item(item, 'values')
                        if item_values[1] == addr:  # 地址现在是第二列
                            # 更新余额和交易数
                            new_values = (
                                item_values[0], 
                                addr, 
                                balance_results.get(addr, '-'), 
                                tx_results.get(addr, '-')
                            )
                            self.result_table.item(item, values=new_values)
                            break
                    else:
                        # 如果表格中没有找到对应地址，添加新行
                        self.result_table.insert('', tk.END, values=(
                            idx, 
                            addr, 
                            balance_results.get(addr, '-'), 
                            tx_results.get(addr, '-')
                        ))
                
                # 显示日志
                self.log(f"已完成 {len(self.wallets)} 个钱包的余额和交易数查询")
                
            except Exception as e:
                # 出错时也要停止进度指示器
                self.stop_progress_indicator()
                self.log(f"查询过程中发生错误: {str(e)}")
        
        # 启动线程执行查询
        thread = threading.Thread(target=query_task)
        thread.daemon = True
        thread.start()
    
    def export_results(self):
        """导出查询结果"""
        if not self.result_table.get_children():
            messagebox.showinfo("提示", "没有结果可导出")
            return
            
        # 选择保存文件
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        # 启动进度指示器
        self.start_progress_indicator("正在导出数据")
        
        def export_task():
            try:
                # 获取表格数据
                data = []
                for item in self.result_table.get_children():
                    values = self.result_table.item(item, 'values')
                    data.append({
                        '序号': values[0],
                        '钱包地址': values[1],
                        '余额 (MON)': values[2],  # 余额已经被格式化
                        '交易数': values[3]
                    })
                
                # 创建DataFrame并导出为CSV
                df = pd.DataFrame(data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                # 停止进度指示器
                self.stop_progress_indicator()
                self.log(f"结果已导出至: {file_path}")
            except Exception as e:
                # 出错时也要停止进度指示器
                self.stop_progress_indicator()
                self.log(f"导出失败: {str(e)}")
        
        # 启动线程执行导出
        thread = threading.Thread(target=export_task)
        thread.daemon = True
        thread.start()
    
    def clear_log(self):
        """清除日志区域"""
        self.stop_progress_indicator()  # 确保停止任何进度指示器
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def save_wallets(self):
        """保存钱包列表到文件"""
        try:
            with open(self.wallets_file, 'w') as f:
                json.dump(self.wallets, f)
            self.log(f"钱包列表已保存至: {self.wallets_file}")
        except Exception as e:
            self.log(f"保存钱包列表失败: {str(e)}")
            # 尝试创建目录并重试一次
            try:
                os.makedirs(os.path.dirname(self.wallets_file), exist_ok=True)
                with open(self.wallets_file, 'w') as f:
                    json.dump(self.wallets, f)
                self.log(f"重试保存成功: {self.wallets_file}")
            except Exception as e2:
                self.log(f"重试保存仍然失败: {str(e2)}")
    
    def load_wallets(self):
        """从文件加载钱包列表"""
        try:
            if os.path.exists(self.wallets_file):
                with open(self.wallets_file, 'r') as f:
                    self.wallets = json.load(f)
                self.update_result_table()
                self.log(f"已加载 {len(self.wallets)} 个保存的钱包地址")
            else:
                self.log("没有找到保存的钱包列表")
        except Exception as e:
            self.log(f"加载钱包列表失败: {str(e)}")
            # 如果加载失败，确保钱包列表为空
            self.wallets = []

if __name__ == "__main__":
    root = tk.Tk()
    app = MonadWalletTool(root)
    root.mainloop() 