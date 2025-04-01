import requests
import json
import os
import time
from typing import List, Dict, Any, Tuple, Optional

class LLMCodeAnalyzer:
    """
    LLM을 사용하여 버그 리포트와 소스코드의 관련성을 분석하는 클래스
    """
    
    def __init__(self, api_url: str = "http://192.168.102.166:1234", 
                 model_name: str = "eeve-korean-instruct-10.8b-v1.0",
                 knowledge_file: str = None,
                 script_dir: str = None):
        """
        LLM 코드 분석기 초기화
        
        Args:
            api_url: LLM API 서버 주소
            model_name: 사용할 모델 이름
            knowledge_file: 개발자 지식 파일 경로 (없으면 기본값 사용)
            script_dir: 게임 스크립트 파일 디렉토리 경로
        """
        self.api_url = api_url.rstrip("/") + "/v1/chat/completions"
        self.model_name = model_name
        self.headers = {"Content-Type": "application/json"}
        
        # 개발자 지식 로드
        self.dev_knowledge = self.load_developer_knowledge(knowledge_file) if knowledge_file else {}
        
        # 게임 스크립트 로드
        self.game_scripts = self.load_game_scripts(script_dir) if script_dir else {}
        
        # 연결 테스트
        self.test_connection()
    
    def test_connection(self) -> bool:
        """LLM 서버 연결 테스트"""
        try:
            print(f"[🔄] LLM 서버 연결 테스트 중 ({self.api_url})...")
            
            # 간단한 프롬프트로 연결 테스트
            response = self.ask_llm("안녕하세요", max_tokens=10)
            if response:
                print(f"[✅] LLM 서버 연결 성공 (모델: {self.model_name})")
                return True
            else:
                print(f"[❌] LLM 응답 없음")
                return False
                
        except Exception as e:
            print(f"[❌] LLM 서버 연결 실패: {e}")
            return False
    
    def ask_llm(self, prompt: str, system_prompt: str = None, 
                temperature: float = 0.3, max_tokens: int = 2000, 
                timeout: int = 60) -> Optional[str]:
        """
        LLM API에 질문하고 응답 받기
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (없으면 기본값 사용)
            temperature: 온도 (창의성 정도, 낮을수록 결정적인 응답)
            max_tokens: 최대 토큰 수
            timeout: API 요청 타임아웃 (초)
            
        Returns:
            LLM 응답 텍스트 또는 오류 시 None
        """
        if system_prompt is None:
            system_prompt = "당신은 전문 소프트웨어 개발자이자 버그 분석가입니다. 버그 리포트와 코드를 분석하여 문제 원인을 파악합니다."
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print(f"[⚠️] 유효하지 않은 LLM 응답 형식: {result}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"[⚠️] LLM API 요청 시간 초과 ({timeout}초)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[❌] LLM API 요청 오류: {e}")
            return None
        except Exception as e:
            print(f"[❌] 예상치 못한 오류: {e}")
            return None

    def analyze_bug_report(self, report_text: str) -> Dict[str, Any]:
        """
        버그 리포트를 분석하여 주요 키워드, 의심되는 함수, 영향받는 기능 등을 추출
        
        Args:
            report_text: 버그 리포트 텍스트
            
        Returns:
            분석 결과 딕셔너리
        """
        print(f"[🔍] 버그 리포트 분석 중... ({len(report_text)} 문자)")
        
        prompt = f"""
다음은 소프트웨어 버그 리포트입니다. 리포트를 분석하여 다음 정보를 JSON 형식으로 제공해주세요:

1. 주요 키워드 (영어 및 한글 모두 포함, 최대 10개)
2. 의심되는 함수 또는 메소드 이름 (리포트에서 추론 가능한 경우)
3. 버그 유형 (메모리 누수, 크래시, UI 오류 등으로 분류)
4. 버그 심각도 (상/중/하)
5. 버그 요약 (3줄 이내)

---
버그 리포트:
{report_text}
---

JSON 형식으로 응답해주세요:
```json
{{
  "keywords": ["키워드1", "키워드2", ...],
  "suspected_functions": ["함수1", "함수2", ...],
  "bug_type": "버그 유형",
  "severity": "심각도",
  "summary": "버그 요약"
}}
```

추론이 불가능한 항목은 빈 배열이나 "알 수 없음"으로 표시하세요.
JSON 형식만 반환하고, 다른 설명은 포함하지 마세요.
"""
        try:
            response = self.ask_llm(prompt)
            if not response:
                print("[❌] 버그 리포트 분석 실패: LLM 응답 없음")
                return self._create_default_analysis()
            
            # JSON 추출 (응답이 ```json으로 감싸져 있을 수 있음)
            json_str = self._extract_json(response)
            analysis = json.loads(json_str)
            
            print(f"[✅] 버그 리포트 분석 완료")
            print(f"  - 키워드: {', '.join(analysis.get('keywords', [])[:5])}{'...' if len(analysis.get('keywords', [])) > 5 else ''}")
            print(f"  - 의심 함수: {', '.join(analysis.get('suspected_functions', []))}")
            print(f"  - 버그 유형: {analysis.get('bug_type', '알 수 없음')}")
            
            return analysis
            
        except Exception as e:
            print(f"[❌] 버그 리포트 분석 중 오류 발생: {e}")
            return self._create_default_analysis()
    
    def match_with_code_context(self, bug_analysis: Dict[str, Any], code_chunks: List[Dict[str, Any]], 
                               top_n: int = 5) -> List[Dict[str, Any]]:
        """
        버그 분석 결과와 코드 청크를 비교하여 가장 관련성 높은 코드 영역 추천
        """
        if not bug_analysis or not code_chunks:
            return []
        
        print(f"[🔄] 코드 문맥 분석 중... (코드 청크: {len(code_chunks)}개)")
        
        # 개발자 지식과 게임 스크립트 정보 포맷팅
        context_knowledge = self._format_context_knowledge()
        
        # 1. 의심 함수나 키워드가 직접 포함된 코드 청크 먼저 필터링
        filtered_chunks = self._prefilter_chunks(bug_analysis, code_chunks)
        print(f"[ℹ️] 키워드 일치 코드 청크: {len(filtered_chunks)}개")
        
        # 청크가 너무 많으면 일부만 처리 (LLM 컨텍스트 제한 고려)
        chunks_to_analyze = filtered_chunks[:min(len(filtered_chunks), 10)]
        print(f"[ℹ️] LLM 분석 대상 코드 청크: {len(chunks_to_analyze)}개")
        
        # 결과를 저장할 리스트
        ranked_chunks = []
        
        # 2. LLM을 사용하여 각 코드 청크의 버그 관련성 평가
        for i, chunk in enumerate(chunks_to_analyze):
            file_name = os.path.basename(chunk['file_path'])
            print(f"[🔍] 코드 분석 중: {file_name} ({i+1}/{len(chunks_to_analyze)})")
            
            # 코드 청크가 너무 길면 짧게 자름 (LLM 컨텍스트 한계 고려)
            code_content = chunk['content']
            if len(code_content) > 3000:
                code_content = code_content[:3000] + "...(중략)..."
            
            # 7B 모델에 최적화된 프롬프트 - 개발자 지식 추가
            prompt = f"""
당신은 C++ 코드를 분석하는 도구입니다. 아래 지시를 정확히 따르세요.

[작업]
주어진 코드가 버그와 관련되어 있는지 분석하세요.

[버그 정보]
- 키워드: {', '.join(bug_analysis.get('keywords', []))}
- 문제 요약: {bug_analysis.get('summary', '알 수 없음')}

[코드 정보]
- 파일: {os.path.basename(chunk['file_path'])}
- 위치: {chunk['start_line']}~{chunk['end_line']}줄

[컨텍스트 지식]
{context_knowledge}

[코드]
```cpp
{code_content}
```

⚠️ 중요 지침 ⚠️:
- 오직 제공된 코드 내용만을 바탕으로 분석하세요.
- 컨텍스트 지식은 개념이나 용어 이해를 위한 참고로만 사용하세요.
- 존재하지 않는 함수, 클래스 또는 변수를 언급하지 마세요.
- 추측하지 말고 코드에 명시적으로 나타난 것만 참조하세요.
- 확신이 없는 경우 "알 수 없음" 또는 "확실하지 않음"이라고 명시하세요.
- 참조하는 모든 코드에 대해 정확한 줄 번호를 명시하세요 (예: "42번 줄의 함수 호출").

다음 JSON 형식으로만 응답해주세요:

```json
{{{{
  "relevance_score": 0-10 사이의 점수(높을수록 관련성 높음),
  "reasoning": "이 코드가 버그와 관련이 있거나 없는 이유에 대한 간략한 설명",
  "suspected_lines": [명확한 근거가 있는 의심스러운 라인 번호만 포함, 없으면 빈 배열],
  "referenced_code": [
    {{
      "line": 정확한 라인 번호,
      "code": "실제 해당 라인의 코드",
      "reason": "이 코드가 의심되는 이유"
    }}
  ],
  "confidence": "높음/중간/낮음 (분석의 확신도)"
}}}}
```

오직 JSON 형식만 반환하고 다른 설명이나 주석은 포함하지 마세요.
"""
            try:
                response = self.ask_llm(prompt)
                if not response:
                    continue
                
                # JSON 추출 및 파싱
                json_str = self._extract_json(response)
                analysis_result = json.loads(json_str)
                
                # 분석 결과 저장
                chunk_result = chunk.copy()
                chunk_result.update({
                    'relevance_score': analysis_result.get('relevance_score', 0),
                    'reasoning': analysis_result.get('reasoning', '분석 결과 없음'),
                    'suspected_lines': analysis_result.get('suspected_lines', []),
                    'referenced_code': analysis_result.get('referenced_code', []),
                    'confidence': analysis_result.get('confidence', '알 수 없음')
                })
                
                ranked_chunks.append(chunk_result)
                
                # 잠시 대기 (API 요청 제한 방지)
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[⚠️] 코드 청크 분석 중 오류: {e}")
                continue
        
        # 3. 관련성 점수로 정렬하고 상위 N개 반환
        ranked_chunks.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        top_results = ranked_chunks[:top_n]
        
        print(f"[✅] 코드 문맥 분석 완료")
        for i, result in enumerate(top_results, 1):
            file_name = os.path.basename(result['file_path'])
            print(f"  #{i}: {file_name} (점수: {result.get('relevance_score', 0)}/10)")
        
        return top_results
    
    def generate_fix_suggestion(self, bug_report: str, top_match: Dict[str, Any]) -> str:
        """
        가장 관련성 높은 코드에 대한 수정 제안 생성
        """
        if not top_match:
            return "관련 코드가 충분하지 않아 수정 제안을 생성할 수 없습니다."
        
        file_name = os.path.basename(top_match['file_path'])
        code_content = top_match['content']
        
        # 코드가 너무 길면 자르기
        if len(code_content) > 3000:
            code_content = code_content[:3000] + "...(이하 생략)..."
        
        # 7B 모델에 최적화된 프롬프트
        prompt = f"""
당신은 C++ 개발자입니다. 다음 단계에 따라 버그 수정 방안을 제시하세요.

[버그 리포트]
{bug_report}

[문제 코드]
파일: {file_name}
위치: {top_match['start_line']}~{top_match['end_line']}줄

```cpp
{code_content}
```

[의심되는 부분]
{', '.join(map(str, top_match.get('suspected_lines', [])))}번 줄

[분석 단계]
1. 제공된 코드만 참조하세요.
2. 코드에 명시적으로 보이는 내용만 언급하세요.
3. 모든 줄 번호는 {top_match['start_line']}부터 시작하여 계산하세요.
4. 확신이 없는 경우에는 "확실하지 않음"이라고 명시하세요.

[응답 형식]
1. 파일 정보:
   파일명: {file_name}
   코드 위치: {top_match['start_line']}~{top_match['end_line']}줄

2. 버그 위치:
   (의심되는 정확한 줄 번호와 해당 코드를 인용하세요)

3. 버그 원인:
   (제공된 코드에 명시적으로 보이는 문제만 설명하세요)

4. 수정 방법:
   (가능한 경우 구체적인 코드 수정 방법을 제시하세요)

5. 추가 확인 사항:
   (더 조사가 필요한 부분이 있다면 언급하세요)
"""
        
        try:
            response = self.ask_llm(prompt, max_tokens=2000, temperature=0.5)
            if not response:
                return "수정 제안 생성에 실패했습니다."
            
            print(f"[✅] 수정 제안 생성 완료 ({len(response)} 문자)")
            return response
            
        except Exception as e:
            print(f"[❌] 수정 제안 생성 중 오류: {e}")
            return f"수정 제안 생성 중 오류 발생: {e}"
    
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
            content = chunk['content'].lower()
            
            # 검색어가 코드 내용에 포함되어 있는지 확인
            if any(term.lower() in content for term in search_terms):
                filtered.append(chunk)
        
        # 필터링된 결과가 너무 적으면 원본 청크 반환
        return filtered if filtered else code_chunks
    
    def _extract_json(self, text: str) -> str:
        """LLM 응답에서 JSON 부분 추출"""
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
            # 가장 마지막 닫는 괄호 찾기
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

    def load_developer_knowledge(self, file_path: str = "dev_knowledge.txt") -> Dict[str, List[Dict[str, str]]]:
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
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    # 주석이나 빈 줄 처리
                    if "클래스" in line or "구조체" in line:
                        current_category = "classes"
                    elif "함수" in line:
                        current_category = "functions"
                    elif "버그" in line:
                        current_category = "bugs"
                    continue
                    
                # 콤마로 구분된 항목 처리
                parts = line.split(',', 1)
                if len(parts) == 2:
                    key, description = parts[0].strip(), parts[1].strip()
                    knowledge[current_category].append({
                        "name": key,
                        "description": description
                    })
            
            print(f"[✅] 개발자 지식 로드 완료: {sum(len(v) for v in knowledge.values())}개 항목")
            
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

    def _format_context_knowledge(self) -> str:
        """
        개발자 지식과 게임 스크립트 정보를 포함하는 형식으로 포맷팅
        """
        context_parts = []
        
        # 1. 개발자 지식 포맷팅
        if self.dev_knowledge:
            dev_knowledge_text = []
            
            # 클래스 정보
            if self.dev_knowledge.get("classes"):
                dev_knowledge_text.append("- 클래스 및 구조체 정보:")
                for item in self.dev_knowledge["classes"][:10]:  # 너무 길지 않게 제한
                    dev_knowledge_text.append(f"  * {item['name']}: {item['description']}")
            
            # 함수 정보
            if self.dev_knowledge.get("functions"):
                dev_knowledge_text.append("- 주요 함수 정보:")
                for item in self.dev_knowledge["functions"][:10]:
                    dev_knowledge_text.append(f"  * {item['name']}: {item['description']}")
            
            # 버그 유형 정보
            if self.dev_knowledge.get("bugs"):
                dev_knowledge_text.append("- 알려진 버그 유형:")
                for item in self.dev_knowledge["bugs"]:
                    dev_knowledge_text.append(f"  * {item['name']}: {item['description']}")
            
            if dev_knowledge_text:
                context_parts.append("## 개발자 제공 지식\n" + "\n".join(dev_knowledge_text))
        
        # 2. 게임 스크립트 정보 포맷팅
        if self.game_scripts and any(self.game_scripts.values()):
            script_text = ["## 게임 스크립트 정보"]
            
            # 각 카테고리별 샘플 정보 추가
            for category, scripts in self.game_scripts.items():
                if scripts:
                    script_text.append(f"- {category.title()} 스크립트 ({len(scripts)}개):")
                    
                    # 각 카테고리에서 최대 3개 파일만 샘플로 추가
                    for script in scripts[:3]:
                        file_name = script.get('file', 'unknown')
                        content = script.get('content', {})
                        
                        # 스크립트 내용에서 대표적인 몇 개 항목만 포함
                        sample_entries = []
                        for section, entries in content.items():
                            if entries and len(entries) > 0:
                                sample_entries.append(f"    * {section}: {entries[0].get('value', '')}")
                                if len(entries) > 1:
                                    sample_entries.append(f"    * {section}: {entries[1].get('value', '')}")
                                    
                        if sample_entries:
                            script_text.append(f"  * {file_name}:")
                            script_text.extend(sample_entries[:3])  # 최대 3개 샘플만
            
            if len(script_text) > 1:  # 헤더만 있는 경우는 제외
                context_parts.append("\n".join(script_text))
        
        # 모든 컨텍스트 병합
        if context_parts:
            return "\n\n".join(context_parts)
        else:
            return "추가 컨텍스트 정보 없음"

    def load_game_scripts(self, script_dir: str) -> Dict[str, Any]:
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
            
            # 각 파일 처리
            for script_file in script_files:
                file_name = os.path.basename(script_file)
                category = self._determine_script_category(file_name)
                
                try:
                    # 다양한 인코딩 시도 (대부분 ANSI/CP949 사용)
                    content = self._read_file_with_encoding(script_file)
                    
                    if content:
                        # 스크립트 파일 내용 파싱
                        parsed_content = self._parse_script_content(content, file_name)
                        
                        if parsed_content:
                            scripts[category].append({
                                'file': file_name,
                                'content': parsed_content
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
        
        if any(kw in file_name_lower for kw in ['dialog', 'conversation', 'talk']):
            return 'dialogs'
        elif any(kw in file_name_lower for kw in ['quest', 'mission']):
            return 'quests'
        elif any(kw in file_name_lower for kw in ['item', 'equip', 'weapon']):
            return 'items'
        elif any(kw in file_name_lower for kw in ['skill', 'ability', 'spell']):
            return 'skills'
        else:
            return 'misc'

    def _read_file_with_encoding(self, file_path: str) -> str:
        """다양한 인코딩을 시도하여 파일 읽기"""
        encodings = ['cp949', 'euc-kr', 'utf-8']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception:
                break
        
        # 바이너리 모드로 시도
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                # 인코딩 추측 시도
                return content.decode('cp949', errors='replace')
        except Exception as e:
            print(f"[⚠️] 파일 읽기 실패: {file_path} - {e}")
            return ""

    def _parse_script_content(self, content: str, file_name: str) -> Dict[str, Any]:
        """스크립트 파일 내용 파싱"""
        # 간단한 키-값 페어 파싱
        result = {}
        
        # 줄 단위로 파싱
        lines = content.split('\n')
        current_section = "default"
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # 섹션 헤더 확인
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].strip()
                result[current_section] = []
                continue
            
            # 키-값 쌍 파싱
            if '=' in line:
                key, value = line.split('=', 1)
                if current_section in result:
                    result[current_section].append({
                        'key': key.strip(),
                        'value': value.strip()
                    })
            else:
                # 일반 텍스트인 경우
                if current_section in result:
                    result[current_section].append({
                        'key': '',
                        'value': line
                    })
        
        return result

# 직접 실행 테스트용
if __name__ == "__main__":
    analyzer = LLMCodeAnalyzer()
    
    # 간단한 테스트
    print("\n=== LLM 연결 테스트 ===")
    test_prompt = "C++에서 메모리 누수의 주요 원인은 무엇인가요? 간단히 답변해주세요."
    response = analyzer.ask_llm(test_prompt)
    print(f"LLM 테스트 응답: {response[:100]}...")