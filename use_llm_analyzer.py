import os
import argparse
from llm_code_analyzer import LLMCodeAnalyzer
from typing import List, Dict, Any

# llm 기반 코드 분석기
# 버그 리포트 분석 후 소스코드 분석 후 매칭
# 컨텍스트 지식 활용
# 게임 스크립트 활용
# 코드 청크 분할
# 참조 코드 출력
# 분석 신뢰도 표시
# 수정 제안 생성

def load_bug_report(file_path: str) -> str:
    """버그 리포트 파일 로드"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[❌ 오류] 버그 리포트 로드 실패: {e}")
        return ""

def load_source_files(directory: str, extensions=('.cpp', '.h')) -> List[Dict[str, Any]]:
    """소스 파일 로드 및 청크로 분할"""
    chunks = []
    
    print(f"[🔍] {directory} 에서 소스 파일 스캔 중...")
    
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(extensions):
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
    parser = argparse.ArgumentParser(description='LLM 기반 코드 분석 도구')
    parser.add_argument('--bug_report', type=str, default="D:/data/GersangDebugAutomation/bug_report.txt",
                        help='버그 리포트 파일 경로')
    parser.add_argument('--source_dir', type=str, default="C:/data/Branch_Trunk_bugfix",
                        help='소스 코드 디렉토리 경로')
    parser.add_argument('--knowledge', type=str, default="dev_knowledge.txt",
                        help='개발자 지식 파일 경로 (없으면 기본 분석 진행)')
    parser.add_argument('--api_url', type=str, default="http://192.168.102.166:1234",
                        help='LLM API 서버 주소')
    parser.add_argument('--model', type=str, default="eeve-korean-instruct-10.8b-v1.0",
                        help='사용할 LLM 모델 이름')
    parser.add_argument('--script_dir', type=str, default="C:/data/GCS",
                        help='게임 스크립트 파일 디렉토리 경로')
    
    args = parser.parse_args()
    
    # 경로 설정
    bug_report_path = args.bug_report
    source_dir = args.source_dir
    knowledge_file = args.knowledge if os.path.exists(args.knowledge) else None
    script_dir = args.script_dir if os.path.exists(args.script_dir) else None
    
    if knowledge_file:
        print(f"[📚] 개발자 지식 파일: {knowledge_file}")
    else:
        print(f"[ℹ️] 개발자 지식 파일({args.knowledge})이 없습니다. 기본 분석을 진행합니다.")
    
    if script_dir:
        print(f"[📜] 게임 스크립트 디렉토리: {script_dir}")
    else:
        print(f"[ℹ️] 게임 스크립트 디렉토리({args.script_dir})가 존재하지 않습니다.")
    
    # 1. 버그 리포트 로드
    print(f"\n[📄] 버그 리포트 로드 중: {bug_report_path}")
    bug_report = load_bug_report(bug_report_path)
    if not bug_report:
        print("[❌] 버그 리포트가 비어있습니다. 종료합니다.")
        return
    
    # 2. LLM 분석기 초기화
    print("\n[🤖] LLM 코드 분석기 초기화 중...")
    analyzer = LLMCodeAnalyzer(
        api_url=args.api_url,
        model_name=args.model,
        knowledge_file=knowledge_file,
        script_dir=script_dir
    )
    
    # 3. 버그 리포트 분석
    print("\n[🔍] 버그 리포트 분석 중...")
    bug_analysis = analyzer.analyze_bug_report(bug_report)
    
    # 4. 소스 코드 로드
    print("\n[📂] 소스 코드 로드 중...")
    code_chunks = load_source_files(source_dir)
    if not code_chunks:
        print("[❌] 소스 코드 로드에 실패했습니다. 종료합니다.")
        return
    
    # 5. 코드 문맥 매칭
    print("\n[🔄] 코드 문맥 분석 중...")
    matching_chunks = analyzer.match_with_code_context(bug_analysis, code_chunks, top_n=5)
    
    # 6. 결과 출력
    print("\n[📊] === 분석 결과 ===")
    print(f"버그 유형: {bug_analysis.get('bug_type', '알 수 없음')}")
    print(f"심각도: {bug_analysis.get('severity', '알 수 없음')}")
    print(f"버그 요약: {bug_analysis.get('summary', '알 수 없음')}")
    print(f"관련 키워드: {', '.join(bug_analysis.get('keywords', ['없음']))}")
    
    print("\n[🔍] 의심 코드 영역:")
    for i, chunk in enumerate(matching_chunks, 1):
        file_path = chunk['file_path']
        file_name = os.path.basename(file_path)
        
        print(f"\n{i}. 파일: {file_name}")
        print(f"   전체 경로: {file_path}")
        print(f"   코드 위치: {chunk['start_line']}~{chunk['end_line']} 라인")
        
        # 의심 라인 정보 출력
        suspected_lines = chunk.get('suspected_lines', [])
        if suspected_lines:
            print(f"   의심 라인: {', '.join(map(str, suspected_lines))}")
            
            # 참조된 코드 출력 (새로운 형식)
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
    
    # 7. 최상위 매칭에 대한 수정 제안 생성
    if matching_chunks:
        print("\n[💡] 수정 제안 생성 중...")
        fix_suggestion = analyzer.generate_fix_suggestion(bug_report, matching_chunks[0])
        print("\n[🛠️] 수정 제안:")
        print(fix_suggestion)
    
    print("\n[✅] 분석 완료")

if __name__ == "__main__":
    main() 