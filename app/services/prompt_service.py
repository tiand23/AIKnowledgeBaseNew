"""
Prompt 服务 - 管理 Prompt 模板和构建
"""
from typing import List, Dict, Optional
from datetime import datetime
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PromptService:
    
    def __init__(self):
        self.templates = {
            "knowledge_qa": {
                "template": """あなたは社内ナレッジベースに接続されたアシスタントです。

回答時は次のルールを厳守してください。
1. 必ず提供された参照情報を根拠に回答する。
2. 根拠が不足する場合は、不足していることを明確に示す。
3. 回答は簡潔・正確・客観的に記述する。
4. 根拠の参照は [文書X] 形式で示す。
5. 質問が「直近N件の案件/経歴/役割」の場合、必ず新しい順に整理する（職歴/経歴/担当/役割を根拠にしてよい）。
6. 表記ゆれ（例: 簡体/繁体、全角/半角、かな/漢字）だけで否定せず、同一対象の可能性を検討する。
7. 「現在からどれくらい前か」を問われた場合は、today={today} を基準に計算して年月を示す。

参照情報:
{context}

文書ソース:
{sources}

会話履歴:
{history}

ユーザー質問: {query}

日本語で回答し、参照した文書を必ず明記してください。""",
                "variables": ["context", "history", "query", "sources"],
                "max_tokens": 4000
            },
            "simple_qa": {
                "template": """あなたは社内アシスタントです。

会話履歴:
{history}

ユーザー質問: {query}

日本語で回答してください。""",
                "variables": ["history", "query"],
                "max_tokens": 2000
            }
        }
    
    def get_template(self, template_name: str) -> Optional[Dict]:
        """
        获取模板配置
        
        Args:
            template_name: 模板名称
            
        Returns:
            模板配置，如果不存在返回None
        """
        return self.templates.get(template_name)
    
    def build_prompt(
        self,
        template_name: str,
        context: str = "",
        history: List[Dict] = None,
        query: str = "",
        sources: List[Dict] = None
    ) -> str:
        """
        构建Prompt
        
        Args:
            template_name: 模板名称
            context: 检索到的上下文信息
            history: 对话历史列表
            query: 用户问题
            sources: 文档来源列表
            
        Returns:
            构建好的Prompt字符串
        """
        template_config = self.get_template(template_name)
        if not template_config:
            logger.warning(f"模板 {template_name} 不存在，使用默认模板")
            template_config = self.templates["knowledge_qa"]
        
        template_str = template_config["template"]
        history = history or []
        sources = sources or []
        
        history_str = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in history[-5:]
        ]) if history else "なし"
        
        sources_str = "\n".join([
            f"[文書{i+1}] {source.get('file_name', '不明なファイル')}"
            for i, source in enumerate(sources)
        ]) if sources else "なし"
        
        params = {
            "context": context or "関連する参照情報は見つかりませんでした。",
            "history": history_str,
            "query": query,
            "sources": sources_str,
            "today": datetime.now().strftime("%Y-%m-%d")
        }
        
        try:
            prompt = template_str.format(**params)
            logger.debug(f"构建Prompt成功: 模板={template_name}, 上下文长度={len(context)}")
            return prompt
        except KeyError as e:
            logger.error(f"构建Prompt失败: 缺少变量 {e}")
            return f"ユーザー質問: {query}\n\n回答してください。"
    
    def build_rag_prompt(
        self,
        context: str,
        history: List[Dict],
        query: str,
        sources: List[Dict]
    ) -> str:
        """
        构建RAG Prompt（便捷方法）
        
        Args:
            context: 检索到的上下文
            history: 对话历史
            query: 用户问题
            sources: 文档来源
            
        Returns:
            Prompt字符串
        """
        return self.build_prompt(
            template_name="knowledge_qa",
            context=context,
            history=history,
            query=query,
            sources=sources
        )
    
    def format_history_for_llm(self, history: List[Dict]) -> List[Dict[str, str]]:
        """
        将对话历史格式化为LLM需要的格式
        
        Args:
            history: 对话历史列表（包含role, content, timestamp）
            
        Returns:
            LLM格式的消息列表
        """
        messages = []
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg.get("content", "")
                })
        return messages


prompt_service = PromptService()
