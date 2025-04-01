import os
import json
import time
import requests
import re
from typing import Dict, Any, List, Optional

class MultiLLMCodeAnalyzer:
    """
    여러 개의 LLM을 활용하여 버그 리포트와 소스코드의 관련성을 분석하는 클래스
    """
    
    def __init__(self, 
                 translator_url: str = "http://192.168.102.166:1234", 
                 translator_model: str = "eeve-korean-instruct-10.8b-v1.0",
                 knowledge_file: str = None,
                 script_dir: str = None):
        """
        다중 LLM 코드 분석기 초기화
        
        Args:
            translator_url: 번역기 LLM API 서버 주소
            translator_model: 번역기 LLM 모델 이름
            knowledge_file: 개발자 지식 파일 경로 (없으면 기본값 사용)
            script_dir: 게임 스크립트 파일 디렉토리 경로
        """
        # API 설정
        self.translator_url = translator_url.rstrip("/") + "/v1/chat/completions"
        self.translator_model = translator_model
        self.headers = {"Content-Type": "application/json"}
        
        # 코드 분석 LLM 저장소
        self.code_llms = {}
        
        # 기본 데이터 로드
        self.dev_knowledge = self._load_developer_knowledge(knowledge_file) if knowledge_file else {}
        self.game_scripts = self._load_game_scripts(script_dir) if script_dir else {}
        
        # 번역기 연결 테스트
        self._test_translator_connection()
    
    def add_code_llm(self, name: str, api_url: str, model_name: str, specialty: str = "general") -> bool:
        """
        코드 분석용 LLM 추가
        """
        try:
            # LLM 정보를 객체로 저장
            class LLM:
                def __init__(self, name, url, model, specialty):
                    self.name = name
                    self.url = url
                    self.model = model
                    self.specialty = specialty
                
                def ask(self, prompt, system_prompt=None, temperature=0.3, max_tokens=2000):
                    return self._call_llm_api(prompt, system_prompt, temperature, max_tokens)
                
                def _call_llm_api(self, prompt, system_prompt=None, temperature=0.3, max_tokens=2000):
                    if system_prompt is None:
                        system_prompt = "You are a helpful assistant specializing in code analysis."
                    
                    # 프롬프트가 문자열인지 확인하고 필요시 변환
                    if not isinstance(prompt, str):
                        try:
                            prompt = str(prompt)
                        except Exception as e:
                            print(f"[⚠️] 프롬프트 변환 오류: {e}")
                            return None

                    # 프롬프트 길이 제한 및 유효성 확인
                    if len(prompt) > 15000:  # 모델 컨텍스트 제한 고려
                        prompt = prompt[:15000] + "... (텍스트가 너무 길어 잘림)"
                    
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                    
                    # 디버깅 로그
                    print(f"[🔍] LLM 요청 전송: {self.name}, 프롬프트 길이: {len(prompt)} 자, 최대 토큰: {max_tokens}")
                    
                    try:
                        response = requests.post(
                            self.url,
                            headers={"Content-Type": "application/json"},
                            json={
                                "model": self.model,
                                "messages": messages,
                                "temperature": temperature,
                                "max_tokens": max_tokens
                            },
                            timeout=60
                        )
                        
                        print(f"[📡] LLM 응답 상태 코드: {response.status_code}")
                        
                        response.raise_for_status()
                        
                        result = response.json()
                        if "choices" in result and len(result["choices"]) > 0:
                            answer = result["choices"][0]["message"]["content"]
                            print(f"[✅] LLM 응답 수신: {len(answer)} 자")
                            return answer
                        else:
                            print(f"[⚠️] 유효하지 않은 LLM 응답 형식: {result}")
                            return None
                    except Exception as e:
                        print(f"[❌] LLM API 요청 오류: {e}")
                        return None
            
            # URL 형식 확인
            llm_url = api_url.rstrip("/") + "/v1/chat/completions"
            
            # LLM 인스턴스 생성
            llm = LLM(name, llm_url, model_name, specialty)
            
            # 간단한 연결 테스트
            test_prompt = "Write a simple hello world function in Python."
            response = llm.ask(test_prompt, max_tokens=50)
            
            if response:
                print(f"[✅] 코드 분석 LLM '{name}' 추가 및 테스트 성공")
                # 테스트 성공 시 저장
                self.code_llms[name] = llm
                return True
            else:
                print(f"[❌] 코드 분석 LLM '{name}' 테스트 실패")
                return False
                
        except Exception as e:
            print(f"[❌] 코드 분석 LLM '{name}' 추가 중 오류: {e}")
            return False
    
    def analyze_bug_report(self, report_text: str) -> Dict[str, Any]:
        """
        버그 리포트 분석 - 한국어 -> 영어 번역 후 분석, 한국어로 번역
        """
        print(f"[🔍] 버그 리포트 분석 중... ({len(report_text)} 문자)")
        
        # 1. 한국어 -> 영어 번역
        print("[🔄] 버그 리포트 영어 번역 중...")
        english_report = self._translate_to_english(report_text)
        if not english_report:
            print("[❌] 버그 리포트 번역 실패")
            return self._create_default_analysis()
        
        # 2. 영어로 버그 분석 (첫 번째 코드 LLM 사용)
        if not self.code_llms:
            print("[⚠️] 등록된 코드 분석 LLM이 없습니다.")
            return self._create_default_analysis()
        
        # 가장 적합한 LLM 선택 (현재는 첫 번째 LLM 사용)
        code_llm = next(iter(self.code_llms.values()))
        print(f"[🔄] {code_llm.name} 모델로 버그 분석 중...")
        
        analysis_prompt = f"""
Analyze the following bug report and extract key information.
Provide your analysis in JSON format with the following fields:
- keywords: list of keywords (max 10)
- suspected_functions: list of function names mentioned or implied
- bug_type: type of bug (memory leak, crash, UI issue, etc.)
- severity: high/medium/low
- summary: brief summary (max 3 lines)

Bug Report:
{english_report}

Respond only with the JSON.
"""
        
        analysis_result = code_llm.ask(analysis_prompt)
        if not analysis_result:
            print(f"[❌] {code_llm.name} 모델 분석 실패")
            return self._create_default_analysis()
        
        # 3. 결과 파싱 및 한국어로 번역
        try:
            # JSON 추출
            json_str = self._extract_json(analysis_result)
            analysis = json.loads(json_str)
            
            # 요약 부분 한국어로 번역
            if "summary" in analysis:
                print("[🔄] 분석 결과 한국어 번역 중...")
                korean_summary = self._translate_to_korean(analysis["summary"])
                if korean_summary:
                    analysis["summary"] = korean_summary
            
            print(f"[✅] 버그 리포트 분석 완료")
            return analysis
            
        except Exception as e:
            print(f"[❌] 분석 결과 처리 중 오류: {e}")
            return self._create_default_analysis()
    
    def match_with_code_context(self, bug_report: str, bug_analysis: Dict[str, Any], code_chunks: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        버그 리포트와 가장 관련성이 높은 코드 청크를 찾아 반환합니다.
        
        Args:
            bug_report: 원본 버그 리포트 텍스트
            bug_analysis: 버그 분석 결과
            code_chunks: 소스 코드 청크 목록
            top_n: 반환할 최상위 결과 수
            
        Returns:
            관련성 순으로 정렬된 코드 청크 목록 (각 항목은 파일명, 내용, 관련성 점수 포함)
        """
        if not code_chunks:
            print("[⚠️] 코드 청크가 없습니다. 코드 매치를 수행할 수 없습니다.")
            return []
            
        print(f"[🔍] 코드 컨텍스트 매칭 시작 (전체 {len(code_chunks)}개 청크)")
        
        # 버그 분석 결과 확인
        keywords = bug_analysis.get('keywords', [])
        functions = bug_analysis.get('suspected_functions', [])
        summary = bug_analysis.get('summary', '버그 요약 정보 없음')
        
        print(f"[ℹ️] 버그 키워드: {', '.join(keywords) if keywords else '없음'}")
        print(f"[ℹ️] 의심 함수: {', '.join(functions) if functions else '없음'}")
        
        # 코드 청크 사전 필터링
        filtered_chunks = self._prefilter_chunks(bug_analysis, code_chunks)
        print(f"[ℹ️] 사전 필터링 후 {len(filtered_chunks)}/{len(code_chunks)}개 청크 분석 대상")
        
        # 결과 배열
        ranked_matches = []
        
        # 코드 분석 LLM 선택
        if not self.code_llms:
            print("[❌] 사용 가능한 코드 분석 LLM이 없습니다.")
            return []
            
        analysis_llm = None
        for llm in self.code_llms.values():
            if llm.specialty == "analysis" or llm.specialty == "code":
                analysis_llm = llm
                break
        
        # 분석 전문 LLM이 없으면 첫 번째 LLM 사용
        if analysis_llm is None:
            analysis_llm = next(iter(self.code_llms.values()))
            
        print(f"[🧠] 코드 분석에 사용할 LLM: {analysis_llm.name}")
        
        # 청크 그룹화 처리 (한 번에 최대 10개까지 처리)
        chunk_groups = [filtered_chunks[i:i+10] for i in range(0, len(filtered_chunks), 10)]
        
        for group_idx, chunk_group in enumerate(chunk_groups):
            print(f"[🔄] 청크 그룹 {group_idx+1}/{len(chunk_groups)} 분석 중 ({len(chunk_group)}개)")
            
            # LLM에 분석 프롬프트 구성
            prompt = f"""
You are a specialized code analysis agent analyzing bug reports and source code.

I'm going to provide you with bug information and code chunks. Your task is to analyze each code chunk to determine how relevant it is to the bug report.

# BUG INFORMATION
- Keywords: {', '.join(keywords) if keywords else 'No specific keywords'}
- Bug Summary: {summary}

# CODE CHUNKS TO ANALYZE
"""
            
            # 각 코드 청크 정보 추가
            for idx, chunk in enumerate(chunk_group):
                file_name = chunk.get('file', 'Unknown file')
                start_line = chunk.get('start_line', 0)
                end_line = chunk.get('end_line', 0)
                content = chunk.get('content', '').strip()
                
                # 콘텐츠가 너무 길면 자름
                if len(content) > 1500:
                    content = content[:1500] + "... (truncated)"
                
                prompt += f"""
CHUNK {idx+1}:
- File: {file_name}
- Lines: {start_line}-{end_line}
```
{content}
```
"""
            
            # 프롬프트 마무리 - 분석 및 응답 형식 안내
            prompt += """
# ANALYSIS INSTRUCTIONS
For each code chunk, analyze:
1. How relevant it is to the bug description (score from 0-10)
2. Why it might be connected to the bug
3. Any specific code patterns or functions that match with the bug report

# RESPONSE FORMAT
Respond in JSON format as follows:
```json
[
  {
    "chunk_index": 1,
    "relevance_score": 8,
    "reasoning": "This chunk contains the function mentioned in the bug report and handles the problematic scenario",
    "referenced_code": "specific lines or elements from the code that are relevant"
  },
  ...
]
```
Order the chunks by relevance_score from highest to lowest.
"""
            
            # LLM 호출
            try:
                response = analysis_llm.ask(prompt)
                
                # JSON 응답 추출 시도
                try:
                    # "[" 와 "]" 사이의 JSON 데이터 추출
                    json_str = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                    if json_str:
                        json_data = json.loads(json_str.group())
                    else:
                        # "```json" 와 "```" 사이의 데이터 추출 시도
                        json_str = re.search(r'```(?:json)?\s*(\[\s*\{.*\}\s*\])\s*```', response, re.DOTALL)
                        if json_str:
                            json_data = json.loads(json_str.group(1))
                        else:
                            print(f"[⚠️] JSON 형식 응답을 찾을 수 없습니다. 원본 응답: {response[:100]}...")
                            continue
                            
                    # 분석 결과를 코드 청크에 매핑
                    for item in json_data:
                        chunk_idx = item.get('chunk_index', 0) - 1  # 1-indexed to 0-indexed
                        if 0 <= chunk_idx < len(chunk_group):
                            chunk = chunk_group[chunk_idx]
                            
                            # 한국어 번역 시도
                            reasoning_ko = ""
                            referenced_code_ko = ""
                            
                            try:
                                reasoning_ko = self._translate_to_korean(item.get('reasoning', ''))
                                referenced_code_ko = self._translate_to_korean(item.get('referenced_code', ''))
                            except Exception as e:
                                print(f"[⚠️] 번역 중 오류: {e}")
                                reasoning_ko = item.get('reasoning', '')
                                referenced_code_ko = item.get('referenced_code', '')
                            
                            ranked_matches.append({
                                'file': chunk.get('file', ''),
                                'file_path': chunk.get('file_path', ''),
                                'start_line': chunk.get('start_line', 0),
                                'end_line': chunk.get('end_line', 0),
                                'content': chunk.get('content', ''),
                                'relevance_score': item.get('relevance_score', 0),
                                'reasoning': reasoning_ko,
                                'referenced_code': referenced_code_ko
                            })
                    
                except json.JSONDecodeError as e:
                    print(f"[❌] JSON 파싱 오류: {e}")
                    print(f"[ℹ️] 원본 응답: {response[:100]}...")
                
            except Exception as e:
                print(f"[❌] LLM API 요청 오류: {e}")
        
        # 최종 결과 정렬 및 반환
        if ranked_matches:
            ranked_matches.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            print(f"[✅] 코드 컨텍스트 매칭 완료: {len(ranked_matches)}개 결과 찾음")
            
            # 상위 N개 항목만 반환
            return ranked_matches[:top_n]
        else:
            print("[⚠️] 관련 코드를 찾지 못했습니다.")
            
            # 결과가 없으면 원본 청크의 상위 N개를 반환
            default_results = []
            for chunk in code_chunks[:top_n]:
                default_results.append({
                    'file': chunk.get('file', ''),
                    'file_path': chunk.get('file_path', ''),
                    'start_line': chunk.get('start_line', 0),
                    'end_line': chunk.get('end_line', 0),
                    'content': chunk.get('content', ''),
                    'relevance_score': 1,  # 최소 점수
                    'reasoning': '분석 결과가 없어 기본값으로 반환됨',
                    'referenced_code': ''
                })
            return default_results
    
    def generate_fix_suggestion(self, bug_report: str, top_match: Dict[str, Any]) -> str:
        """
        버그 리포트와 가장 관련성이 높은 코드 청크에 대한 수정 제안을 생성합니다.
        
        Args:
            bug_report: 원본 버그 리포트 텍스트
            top_match: 가장 관련성이 높은 코드 청크 정보
            
        Returns:
            코드 수정 제안 문자열
        """
        if not top_match:
            return "관련된 코드를 찾을 수 없어 수정 제안을 생성할 수 없습니다."
            
        # 파일 정보 추출 (file_path 또는 file 키 사용)
        file_path = top_match.get('file_path', top_match.get('file', '알 수 없는 파일'))
        file_name = os.path.basename(file_path) if file_path else '알 수 없는 파일'
        
        # 의심 코드 내용 추출
        code_content = top_match.get('content', '')
        if not code_content:
            return "코드 내용이 없어 수정 제안을 생성할 수 없습니다."
            
        # 코드가 너무 길면 일부만 사용
        if len(code_content) > 3000:
            code_content = code_content[:3000] + "\n// ... (너무 긴 코드는 생략됨) ..."
            
        # 버그 리포트 영어로 번역 시도
        bug_report_en = bug_report
        try:
            bug_report_en = self._translate_to_english(bug_report)
            print("[ℹ️] 버그 리포트 영어 번역 완료")
        except Exception as e:
            print(f"[⚠️] 버그 리포트 번역 중 오류: {e}")
            # 원본 텍스트 유지
        
        # 의심 라인 정보 컴파일
        start_line = top_match.get('start_line', 0)
        end_line = top_match.get('end_line', 0)
        relevance_score = top_match.get('relevance_score', 0)
        reasoning = top_match.get('reasoning', '분석 정보 없음')
        referenced_code = top_match.get('referenced_code', '')
        
        # 최적의 수정 LLM 선택 (fixing 특성 우선)
        if not self.code_llms:
            print("[❌] 사용 가능한 코드 분석 LLM이 없습니다.")
            return "코드 분석 LLM이 없어 수정 제안을 생성할 수 없습니다."
            
        fix_llm = None
        for llm in self.code_llms.values():
            if llm.specialty == "fixing":
                fix_llm = llm
                break
                
        # 수정 전문 LLM이 없으면 첫 번째 LLM 사용
        if fix_llm is None:
            fix_llm = next(iter(self.code_llms.values()))
            
        print(f"[🧠] 코드 수정 제안에 사용할 LLM: {fix_llm.name}")
        
        # 수정 제안 프롬프트 작성
        prompt = f"""
You are an expert C++ bug-fixing assistant. Analyze the bug report and code to suggest a fix.

# Bug Report
{bug_report_en}

# File Information
- File: {file_name}
- Lines: {start_line}-{end_line}
- Relevance Score: {relevance_score}/10
- Analysis: {reasoning}

# Code
```cpp
{code_content}
```

# Additional Information
{referenced_code}

# Task
1. Analyze the code to identify the exact location of the bug
2. Explain the root cause of the bug
3. Provide a specific code fix, showing both the original and fixed code

# Output Format
Respond with the following structure:
1. FILE: [filename]
2. BUG LOCATION: [specific function/line numbers]
3. BUG CAUSE: [clear explanation of why the bug occurs]
4. FIX SUGGESTION: [code snippet showing the fix]
5. ADDITIONAL CHECKS: [any other places to look or considerations]

Your response should be detailed, accurate, and only reference parts of code that are visible in the provided snippet.
Do not invent function names or code that isn't shown in the snippet.
If you cannot determine a fix with confidence, explain what additional information would be needed.
"""
        
        try:
            # LLM 응답 가져오기
            response = fix_llm.ask(prompt)
            
            # 한국어로 번역
            try:
                translated_response = self._translate_to_korean(response)
                print("[✅] 수정 제안 생성 및 번역 완료")
                return translated_response
            except Exception as e:
                print(f"[⚠️] 수정 제안 번역 중 오류: {e}")
                # 번역 실패시 원본 반환
                return response
                
        except Exception as e:
            print(f"[❌] 수정 제안 생성 중 오류: {e}")
            return f"코드 수정 제안 생성 중 오류가 발생했습니다: {e}"
    
    def _test_translator_connection(self) -> bool:
        """번역기 LLM 서버 연결 테스트"""
        try:
            print(f"[🔄] 번역기 LLM 서버 연결 테스트 중...")
            
            # 간단한 번역 테스트
            test_text = "안녕하세요, 테스트입니다."
            english = self._translate_to_english(test_text)
            
            if english:
                print(f"[✅] 번역기 LLM 서버 연결 성공 (모델: {self.translator_model})")
                print(f"  테스트: '{test_text}' -> '{english}'")
                return True
            else:
                print(f"[❌] 번역기 LLM 응답 없음")
                return False
                
        except Exception as e:
            print(f"[❌] 번역기 LLM 서버 연결 실패: {e}")
            return False
    
    def _translate_to_english(self, korean_text: str) -> Optional[str]:
        """한국어를 영어로 번역"""
        system_prompt = "당신은 한국어를 영어로 번역하는 전문가입니다."
        prompt = f"다음 한국어 텍스트를 영어로 번역해주세요:\n\n{korean_text}"
        
        return self._call_translator_llm(system_prompt, prompt)
        
    def _translate_to_korean(self, english_text: str) -> Optional[str]:
        """영어를 한국어로 번역"""
        system_prompt = "당신은 영어를 한국어로 번역하는 전문가입니다."
        prompt = f"다음 영어 텍스트를 한국어로 번역해주세요:\n\n{english_text}"
        
        return self._call_translator_llm(system_prompt, prompt)
    
    def _call_translator_llm(self, system_prompt: str, prompt: str, 
                           temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
        """번역기 LLM API 호출"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": self.translator_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.translator_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"[⚠️] 유효하지 않은 LLM 응답 형식: {result}")
                return None
                
        except Exception as e:
            print(f"[❌] LLM API 요청 오류: {e}")
            return None
    
    def _call_llm(self, llm_name: str, prompt: str, system_prompt: str = None,
                temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
        """코드 분석 LLM API 호출"""
        if llm_name not in self.code_llms:
            print(f"[⚠️] 등록되지 않은 LLM: {llm_name}")
            return None
            
        llm_info = self.code_llms[llm_name]
        url = llm_info["url"]
        model = llm_info["model"]
        
        if system_prompt is None:
            system_prompt = "You are an expert software engineer specializing in code analysis."
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"[⚠️] 유효하지 않은 LLM 응답 형식: {result}")
                return None
                
        except Exception as e:
            print(f"[❌] LLM API 요청 오류: {e}")
            return None
    
    def _extract_json(self, text: str) -> str:
        """텍스트에서 JSON 부분 추출"""
        # JSON 블록 추출 시도
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # 중괄호로 감싸진 부분 찾기
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < end:
                return text[start:end].strip()
        
        # JSON 추출 실패 시 원본 반환
        return text
    
    def _create_default_analysis(self) -> Dict[str, Any]:
        """기본 버그 분석 결과 생성 (분석 실패 시)"""
        return {
            "keywords": [],
            "suspected_functions": [],
            "bug_type": "알 수 없음",
            "severity": "알 수 없음",
            "summary": "분석에 실패했습니다."
        }
    
    def _prefilter_chunks(self, bug_analysis: Dict[str, Any], code_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        버그 분석 키워드/의심 함수가 포함된 코드 청크 필터링
        """
        keywords = bug_analysis.get('keywords', [])
        functions = bug_analysis.get('suspected_functions', [])
        
        # 키워드나 함수가 없으면 모든 청크 반환
        if not keywords and not functions:
            return code_chunks
        
        filtered = []
        search_terms = set(keywords + functions)
        
        for chunk in code_chunks:
            # 파일 경로 키 일관성 유지
            if 'file_path' in chunk and 'file' not in chunk:
                chunk['file'] = chunk['file_path']
            elif 'file' in chunk and 'file_path' not in chunk:
                chunk['file_path'] = chunk['file']
                
            content = chunk['content'].lower()
            
            # 검색어가 코드 내용에 포함되어 있는지 확인
            if any(term.lower() in content for term in search_terms if term):
                filtered.append(chunk)
        
        # 필터링된 결과가 너무 적으면 원본 청크 반환
        return filtered if len(filtered) >= 3 else code_chunks
    
    def _load_developer_knowledge(self, file_path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        개발자가 제공한 도메인 지식을 로드합니다.
        
        Args:
            file_path: 개발자 지식 파일 경로
            
        Returns:
            카테고리별 지식 정보를 담은 딕셔너리
        """
        knowledge = {
            "classes": [],  # 클래스 정보
            "functions": [],  # 함수 정보
            "bugs": [],  # 버그 유형 정보
            "etc": []  # 기타 정보
        }
        
        current_category = "etc"
        
        try:
            print(f"[📚] 개발자 지식 파일 로드 중: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                
                # 빈 줄 무시
                if not line:
                    continue
                    
                # 주석 처리 (카테고리 지정 가능)
                if line.startswith('#'):
                    if "클래스" in line or "구조체" in line:
                        current_category = "classes"
                        print(f"[📚] 클래스/구조체 정보 섹션 발견")
                    elif "함수" in line:
                        current_category = "functions"
                        print(f"[📚] 함수 정보 섹션 발견")
                    elif "버그" in line:
                        current_category = "bugs"
                        print(f"[📚] 버그 유형 정보 섹션 발견")
                    elif "변수" in line:
                        current_category = "etc"
                        print(f"[📚] 변수 정보 섹션 발견")
                    continue
                    
                # 콤마로 구분된 항목 처리 (name,description 형식)
                parts = line.split(',', 1)
                if len(parts) == 2:
                    key, description = parts[0].strip(), parts[1].strip()
                    knowledge[current_category].append({
                        "name": key,
                        "description": description
                    })
            
            total_items = sum(len(v) for v in knowledge.values())
            print(f"[✅] 개발자 지식 로드 완료: {total_items}개 항목")
            
            # 각 카테고리별 항목 수 출력
            for category, items in knowledge.items():
                if items:
                    print(f"  - {category}: {len(items)}개")
            
            return knowledge
        
        except FileNotFoundError:
            print(f"[ℹ️] 개발자 지식 파일({file_path})이 없습니다. 기본 분석을 진행합니다.")
            return knowledge
        except Exception as e:
            print(f"[⚠️] 개발자 지식 로드 중 오류 발생: {e}")
            return knowledge
    
    def _load_game_scripts(self, script_dir: str) -> Dict[str, Any]:
        """
        게임 프로젝트의 스크립트 파일들을 로드합니다.
        
        Args:
            script_dir: 스크립트 파일이 있는 디렉토리 경로
            
        Returns:
            스크립트 정보를 담은 딕셔너리
        """
        scripts = {
            "dialogs": [],       # 대화 스크립트
            "quests": [],        # 퀘스트 정보
            "items": [],         # 아이템 정보
            "skills": [],        # 스킬 정보
            "misc": []           # 기타 스크립트
        }
        
        if not os.path.isdir(script_dir):
            print(f"[⚠️] 스크립트 디렉토리가 존재하지 않습니다: {script_dir}")
            return scripts
        
        print(f"[📜] 게임 스크립트 로드 중: {script_dir}")
        
        try:
            # 디렉토리에서 모든 txt 파일 탐색
            script_files = []
            for root, _, files in os.walk(script_dir):
                for file in files:
                    if file.endswith('.txt'):
                        script_files.append(os.path.join(root, file))
            
            print(f"[ℹ️] 발견된 스크립트 파일: {len(script_files)}개")
            
            # 각 파일 처리 (최대 50개까지만 처리)
            max_files = min(len(script_files), 50)
            for script_file in script_files[:max_files]:
                file_name = os.path.basename(script_file)
                category = self._determine_script_category(file_name)
                
                try:
                    # 다양한 인코딩 시도 (대부분 ANSI/CP949 사용)
                    content = ""
                    for encoding in ['cp949', 'euc-kr', 'utf-8']:
                        try:
                            with open(script_file, 'r', encoding=encoding, errors='replace') as f:
                                content = f.read()
                                break
                        except UnicodeDecodeError:
                            continue
                    
                    if content:
                        # 간단한 파싱 - 섹션과 키-값 쌍 추출
                        sections = {}
                        current_section = "default"
                        sections[current_section] = []
                        
                        for line in content.split('\n'):
                            line = line.strip()
                            
                            # 빈 줄이나 주석 무시
                            if not line or line.startswith('//'):
                                continue
                                
                            # 섹션 헤더 확인 ([섹션명] 형식)
                            if line.startswith('[') and line.endswith(']'):
                                current_section = line[1:-1].strip()
                                if current_section not in sections:
                                    sections[current_section] = []
                                continue
                            
                            # 키-값 쌍 파싱 (key=value 형식)
                            if '=' in line:
                                key, value = line.split('=', 1)
                                sections[current_section].append({
                                    'key': key.strip(),
                                    'value': value.strip()
                                })
                            else:
                                # 일반 텍스트 라인 처리
                                sections[current_section].append({
                                    'key': '',
                                    'value': line
                                })
                        
                        # 섹션 데이터가 비어있지 않은 경우만 추가
                        if any(sections.values()):
                            scripts[category].append({
                                'file': file_name,
                                'content': sections
                            })
                
                except Exception as e:
                    print(f"[⚠️] 스크립트 파일 처리 중 오류: {file_name} - {e}")
                    continue
            
            # 카테고리별 스크립트 수 출력
            for category, items in scripts.items():
                if items:
                    print(f"  - {category}: {len(items)}개 파일")
            
            total_scripts = sum(len(items) for items in scripts.values())
            print(f"[✅] 총 {total_scripts}개 스크립트 파일 로드 완료")
            
            return scripts
        
        except Exception as e:
            print(f"[❌] 스크립트 로드 중 오류 발생: {e}")
            return scripts
            
    def _determine_script_category(self, file_name: str) -> str:
        """파일명을 기반으로 스크립트 카테고리 결정"""
        file_name_lower = file_name.lower()
        
        if any(kw in file_name_lower for kw in ['dialog', 'conversation', 'talk', '대화']):
            return 'dialogs'
        elif any(kw in file_name_lower for kw in ['quest', 'mission', '퀘스트', '임무']):
            return 'quests'
        elif any(kw in file_name_lower for kw in ['item', 'equip', 'weapon', '아이템', '장비', '무기']):
            return 'items'
        elif any(kw in file_name_lower for kw in ['skill', 'ability', 'spell', '스킬', '능력']):
            return 'skills'
        else:
            return 'misc' 