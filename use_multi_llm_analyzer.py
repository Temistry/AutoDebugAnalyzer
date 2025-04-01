import os
import argparse
import json
from multi_llm_analyzer import MultiLLMCodeAnalyzer
from typing import List, Dict, Any

def load_bug_report(file_path):
    """버그 리포트 로드 함수"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[⚠️] {file_path} 파일 로드 중 오류: {e}")
        return None

def load_source_files(source_dir):
    """소스 코드 로드 함수"""
    chunks = []
    
    print(f"[🔍] {source_dir} 경로에서 소스 파일 스캔 중...")
    
    try:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(('.cpp', '.h')):
                    file_path = os.path.join(root, file)
                    
                    try:
                        # ANSI(CP949) 인코딩으로 파일 읽기 시도
                        with open(file_path, 'r', encoding='cp949', errors='replace') as f:
                            content = f.read()
                            
                        # 청크로 분할 (100줄 단위)
                        lines = content.split('\n')
                        chunk_size = 100
                        
                        for i in range(0, len(lines), chunk_size):
                            end_idx = min(i + chunk_size, len(lines))
                            chunk_content = '\n'.join(lines[i:end_idx])
                            
                            if chunk_content.strip():  # 비어있지 않은 경우만
                                chunks.append({
                                    'file_path': file_path,
                                    'start_line': i + 1,
                                    'end_line': end_idx,
                                    'content': chunk_content
                                })
                                
                    except UnicodeDecodeError:
                        # CP949 실패 시 EUC-KR로 시도
                        try:
                            with open(file_path, 'r', encoding='euc-kr', errors='replace') as f:
                                content = f.read()
                                
                            # 같은 청크 분할 로직 반복
                            lines = content.split('\n')
                            for i in range(0, len(lines), chunk_size):
                                end_idx = min(i + chunk_size, len(lines))
                                chunk_content = '\n'.join(lines[i:end_idx])
                                
                                if chunk_content.strip():
                                    chunks.append({
                                        'file_path': file_path,
                                        'start_line': i + 1,
                                        'end_line': end_idx,
                                        'content': chunk_content
                                    })
                        except Exception as e2:
                            print(f"[⚠️] {file_path} 파일 읽기 실패: {e2}")
                    
                    except Exception as e:
                        print(f"[⚠️] {file_path} 파일 처리 중 오류: {e}")
                        
        print(f"[✅] {len(chunks)}개 코드 청크 생성 완료")
        return chunks
        
    except Exception as e:
        print(f"[❌] 소스 파일 스캔 중 오류 발생: {e}")
        return []

def main():
    """메인 실행 함수"""
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='다중 LLM 기반 코드 분석 도구')
    parser.add_argument('--bug_report', type=str, default="D:/data/GersangDebugAutomation/bug_report.txt",
                        help='버그 리포트 파일 경로')
    parser.add_argument('--source_dir', type=str, default="C:/data/Branch_Trunk_bugfix",
                        help='소스 코드 디렉토리 경로')
    parser.add_argument('--knowledge', type=str, default="dev_knowledge.txt",
                        help='개발자 지식 파일 경로 (없으면 기본 분석 진행)')
    parser.add_argument('--script_dir', type=str, default="C:/data/GCS",
                        help='게임 스크립트 파일 디렉토리 경로')
    
    # 번역기 LLM 설정
    parser.add_argument('--translator_url', type=str, default="http://192.168.102.166:1234",
                        help='번역기 LLM API 서버 주소')
    parser.add_argument('--translator_model', type=str, default="eeve-korean-instruct-10.8b-v1.0",
                        help='번역기 LLM 모델 이름')
    
    # 코드 분석 LLM 설정을 위한 인자들
    parser.add_argument('--code_llms', type=str, nargs='+', default=[],
                        help='코드 분석 LLM 정보 (형식: 이름:주소:모델명:전문분야, 예: qwen:http://localhost:1234:Qwen2.5-7B:code)')
    parser.add_argument('--config', type=str, default="config.json",
                        help='LLM 설정 파일 경로')
    
    args = parser.parse_args()
    
    # config.json 파일 로드 시도
    config = {}
    if os.path.exists(args.config):
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"[✅] 설정 파일 로드 완료: {args.config}")
        except Exception as e:
            print(f"[⚠️] 설정 파일 로드 실패: {e}")
    else:
        print(f"[ℹ️] 설정 파일({args.config})이 없습니다. 명령줄 인자를 사용합니다.")
    
    # 경로 설정 (config 값이 있으면 사용, 없으면 명령줄 인자 사용)
    if config and 'defaults' in config:
        defaults = config['defaults']
        bug_report_path = args.bug_report or defaults.get('bug_report_path')
        source_dir = args.source_dir or defaults.get('source_dir')
        knowledge_file = (args.knowledge if os.path.exists(args.knowledge) else defaults.get('knowledge_file')) if os.path.exists(args.knowledge) else None
        script_dir = (args.script_dir if os.path.exists(args.script_dir) else defaults.get('script_dir')) if os.path.exists(args.script_dir) else None
    else:
        bug_report_path = args.bug_report
        source_dir = args.source_dir
        knowledge_file = args.knowledge if os.path.exists(args.knowledge) else None
        script_dir = args.script_dir if os.path.exists(args.script_dir) else None
    
    # 1. 다중 LLM 분석기 초기화
    print("\n[🤖] 다중 LLM 코드 분석기 초기화 중...")
    
    # 번역기 설정 (config 값이 있으면 사용, 없으면 명령줄 인자 사용)
    translator_url = args.translator_url
    translator_model = args.translator_model
    
    if config and 'llm_servers' in config and 'translator' in config['llm_servers']:
        translator_config = config['llm_servers']['translator']
        translator_url = translator_config.get('url', translator_url)
        translator_model = translator_config.get('model', translator_model)
    
    analyzer = MultiLLMCodeAnalyzer(
        translator_url=translator_url,
        translator_model=translator_model,
        knowledge_file=knowledge_file,
        script_dir=script_dir
    )
    
    # 2. 코드 분석 LLM 등록
    code_llms_registered = False
    
    # config.json에서 LLM 등록
    if config and 'llm_servers' in config and 'code_analyzers' in config['llm_servers']:
        code_analyzers = config['llm_servers']['code_analyzers']
        if code_analyzers:
            for llm_config in code_analyzers:
                try:
                    name = llm_config.get('name')
                    url = llm_config.get('url')
                    model = llm_config.get('model')
                    specialty = llm_config.get('specialty', 'general')
                    description = llm_config.get('description', '')
                    
                    if name and url and model:
                        print(f"[🔄] 설정 파일에서 코드 분석 LLM 등록 중: {name} ({description})")
                        analyzer.add_code_llm(name, url, model, specialty)
                        code_llms_registered = True
                    else:
                        print(f"[⚠️] 설정 파일의 LLM 정보가 불완전합니다: {llm_config}")
                except Exception as e:
                    print(f"[⚠️] 설정 파일의 LLM 등록 중 오류: {e}")
    
    # 명령줄 인자에서 LLM 등록 (config.json에서 등록한 것이 없을 때만)
    if not code_llms_registered and args.code_llms:
        for llm_info in args.code_llms:
            try:
                parts = llm_info.split(':')
                if len(parts) >= 3:
                    name = parts[0]
                    url = parts[1]
                    model = parts[2]
                    specialty = parts[3] if len(parts) > 3 else "general"
                    
                    print(f"[🔄] 명령줄 인자에서 코드 분석 LLM 등록 중: {name} ({url}, {model})")
                    analyzer.add_code_llm(name, url, model, specialty)
                    code_llms_registered = True
                else:
                    print(f"[⚠️] 잘못된 LLM 정보 형식: {llm_info}")
            except Exception as e:
                print(f"[❌] LLM 등록 중 오류: {e}")
    
    # 기본 코드 LLM이 없으면 하나 추가
    if not code_llms_registered:
        print("[ℹ️] 코드 분석 LLM이 지정되지 않아 기본 LLM 사용")
        default_url = "http://localhost:1234"
        default_model = "Qwen2.5-Coder-7B-Instruct-Uncensored"
        analyzer.add_code_llm("default-coder", default_url, default_model, "code")
    
    # 3. 버그 리포트 로드
    print(f"\n[📄] 버그 리포트 로드 중: {bug_report_path}")
    bug_report = load_bug_report(bug_report_path)
    if not bug_report:
        print("[❌] 버그 리포트가 비어있습니다. 종료합니다.")
        return
    
    # 4. 버그 리포트 분석
    print("\n[🔍] 버그 리포트 분석 중...")
    bug_analysis = analyzer.analyze_bug_report(bug_report)
    
    # 5. 소스 코드 로드
    print("\n[📂] 소스 코드 로드 중...")
    code_chunks = load_source_files(source_dir)
    if not code_chunks:
        print("[❌] 소스 코드 로드에 실패했습니다. 종료합니다.")
        return
    
    # 6. 코드 문맥 매칭
    print("\n[🔄] 코드 문맥 분석 중...")
    matching_chunks = analyzer.match_with_code_context(bug_report, bug_analysis, code_chunks, top_n=5)
    
    # 매칭된 코드가 없는 경우
    if not matching_chunks:
        print("[⚠️] 버그와 관련된 코드를 찾지 못했습니다.")
        print("\n[✅] 분석 완료")
        return
    
    # 7. 결과 출력
    print("\n[📊] === 분석 결과 ===")
    print(f"버그 유형: {bug_analysis.get('bug_type', '알 수 없음')}")
    print(f"심각도: {bug_analysis.get('severity', '알 수 없음')}")
    print(f"버그 요약: {bug_analysis.get('summary', '알 수 없음')}")
    print(f"관련 키워드: {', '.join(bug_analysis.get('keywords', ['없음']))}")
    
    print("\n[🔍] 의심 코드 영역:")
    for i, chunk in enumerate(matching_chunks, 1):
        # file_path 키가 있으면 사용, 없으면 file 키 사용
        file_path = chunk.get('file_path', chunk.get('file', '알 수 없는 파일'))
        # 상대 경로만 있는 경우 전체 경로 생성
        if '/' not in file_path and '\\' not in file_path and os.path.exists(os.path.join(source_dir, file_path)):
            file_path = os.path.join(source_dir, file_path)
            
        file_name = os.path.basename(file_path)
        
        print(f"\n{i}. 파일: {file_name}")
        print(f"   전체 경로: {file_path}")
        print(f"   코드 위치: {chunk.get('start_line', 0)}~{chunk.get('end_line', 0)} 라인")
        
        # 의심 라인 정보 출력
        suspected_lines = chunk.get('suspected_lines', [])
        if suspected_lines:
            print(f"   의심 라인: {', '.join(map(str, suspected_lines))}")
            
            # 참조된 코드 출력
            referenced_code = chunk.get('referenced_code', [])
            if referenced_code:
                print("\n   참조된 코드:")
                for ref in referenced_code:
                    line_num = ref.get('line', '?')
                    code = ref.get('code', '코드 정보 없음')
                    reason = ref.get('reason', '')
                    print(f"   {line_num}번 줄: {code}")
                    if reason:
                        print(f"      ↳ 이유: {reason}")
        
        # 분석 신뢰도 표시
        confidence = chunk.get('confidence', '알 수 없음')
        print(f"   분석 신뢰도: {confidence}")
        print(f"   관련성 점수: {chunk.get('relevance_score', 0)}/10")
        print(f"   분석: {chunk.get('reasoning', '정보 없음')}")
    
    # 8. 최상위 매칭에 대한 수정 제안 생성
    if matching_chunks:
        print("\n[💡] 수정 제안 생성 중...")
        # 첫 번째 매칭에서 file_path 키 확인
        top_match = matching_chunks[0]
        if 'file_path' not in top_match and 'file' in top_match:
            # file_path 키가 없고 file 키가 있으면 file_path 키 추가
            top_match['file_path'] = top_match['file']
            
        fix_suggestion = analyzer.generate_fix_suggestion(bug_report, top_match)
        print("\n[🛠️] 수정 제안:")
        print(fix_suggestion)
    
    print("\n[✅] 분석 완료")

if __name__ == "__main__":
    main() 