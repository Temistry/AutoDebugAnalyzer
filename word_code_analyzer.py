import os
import re
import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import argparse

#키워드 기반 프로젝트 버그 탐색기
#기계적으로 키워드 추출 후 소스코드 분석 후 매칭

# ===== [모듈 1: 버그리포트 수집] =====
def load_bug_report(file_path):
    """버그 리포트 파일을 로드합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[❌ 오류] 버그 리포트 파일을 읽는 데 실패했습니다: {e}")
        return None

# ===== [모듈 2: 전처리 및 특징 추출] =====
def preprocess_bug_report(report_text):
    """버그 리포트 텍스트를 전처리하고 키워드를 추출합니다."""
    # 한글 단어 추출 (2글자 이상)
    korean_words = re.findall(r'[가-힣]{2,}', report_text)
    
    # 에러 메시지나 함수명 추출 시도 (영문+숫자+특수문자)
    error_patterns = re.findall(r'[A-Za-z0-9_]+\([^)]*\)|[A-Za-z0-9_]+Error|Exception|Bug|[A-Za-z0-9_]+\.cpp|[A-Za-z0-9_]+\.h', report_text)
    
    # 중복 제거 및 병합
    all_keywords = list(set(korean_words + error_patterns))
    
    return {
        'keywords': all_keywords,
        'original_text': report_text
    }

def extract_keywords_with_nlp(report_text):
    """NLP 기반 핵심 키워드 추출 함수 (간단 구현)"""
    # 간단한 구현: 단어 빈도수 기반
    words = re.findall(r'\b[가-힣a-zA-Z0-9_]+\b', report_text)
    word_freq = {}
    
    for word in words:
        if len(word) > 1:  # 1글자 단어 제외
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # 빈도수 기준 상위 10개 키워드 추출
    keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    return [k[0] for k in keywords]

# ===== [모듈 3: 코드 분석 및 매칭] =====
def collect_source_files(src_dir, extensions=('.cpp', '.h')):
    """지정된 디렉토리에서 소스 코드 파일을 수집합니다."""
    source_files = []
    
    print(f"[🔍] {src_dir} 경로에서 소스 파일 수집 중...")
    
    try:
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith(extensions):
                    full_path = os.path.join(root, file)
                    source_files.append(full_path)
        
        print(f"[✅] 총 {len(source_files)}개 소스 파일 발견")
        return source_files
    except Exception as e:
        print(f"[❌ 오류] 소스 파일 수집 중 오류 발생: {e}")
        return []

def parse_code_into_chunks(file_paths, max_chunk_size=100):
    """소스 코드 파일을 청크(Chunk)로 분할합니다."""
    chunks = []
    
    print(f"[🔄] 소스 코드를 청크로 분할 중...")
    
    for file_path in file_paths:
        try:
            # UTF-8에서 CP949(ANSI)로 인코딩 변경
            with open(file_path, 'r', encoding='cp949', errors='replace') as f:
                file_content = f.read()
            
            # 파일을 최대 chunk_size 줄 단위로 분할
            lines = file_content.split('\n')
            total_lines = len(lines)
            
            # 각 청크는 최대 max_chunk_size 줄을 포함
            for i in range(0, total_lines, max_chunk_size):
                end_idx = min(i + max_chunk_size, total_lines)
                chunk_content = '\n'.join(lines[i:end_idx])
                
                # 의미 있는 내용이 있을 경우만 청크로 추가
                if len(chunk_content.strip()) > 0:
                    chunks.append({
                        'file_path': file_path,
                        'start_line': i + 1,
                        'end_line': end_idx,
                        'content': chunk_content
                    })
        except UnicodeDecodeError as e:
            print(f"[⚠️ 경고] {file_path} 파일 인코딩 문제: {e}")
            # CP949 실패 시 다른 인코딩 시도
            try:
                with open(file_path, 'r', encoding='euc-kr', errors='replace') as f:
                    file_content = f.read()
                # 나머지 처리 코드는 동일...
                lines = file_content.split('\n')
                total_lines = len(lines)
                for i in range(0, total_lines, max_chunk_size):
                    end_idx = min(i + max_chunk_size, total_lines)
                    chunk_content = '\n'.join(lines[i:end_idx])
                    if len(chunk_content.strip()) > 0:
                        chunks.append({
                            'file_path': file_path,
                            'start_line': i + 1,
                            'end_line': end_idx,
                            'content': chunk_content
                        })
            except Exception as e2:
                print(f"[❌ 오류] {file_path} 파일 읽기 실패: {e2}")
        except Exception as e:
            print(f"[⚠️ 경고] {file_path} 파일 파싱 중 오류: {e}")
    
    print(f"[✅] {len(chunks)}개 코드 청크 생성 완료")
    return chunks

def create_embeddings(text_list):
    """텍스트 목록에 대한 TF-IDF 임베딩을 생성합니다."""
    print(f"[🔢] 임베딩할 텍스트 수: {len(text_list)}")
    
    # 전체 텍스트 크기 계산 (디버깅용)
    total_text_size = sum(len(t) for t in text_list)
    print(f"[📊] 전체 텍스트 크기: {total_text_size:,} 문자")
    
    # 임베딩 설정 로그
    print(f"[⚙️] 임베딩 설정: n-gram 범위=(1,2), 최대 특성 수=5000, 한글+영문 토큰화")
    
    vectorizer = TfidfVectorizer(
        analyzer='word',
        token_pattern=r'\b[가-힣\w]+\b',  # 한글 및 영문 단어 포함
        ngram_range=(1, 2),  # 단일 단어 및 2단어 구문 포함
        max_features=5000
    )
    
    # 코드 내용에 대한 임베딩 생성
    try:
        print(f"[🧠] TF-IDF 임베딩 변환 중...")
        embeddings = vectorizer.fit_transform(text_list)
        
        # 임베딩 통계 정보 출력
        vocab_size = len(vectorizer.vocabulary_)
        feature_names = vectorizer.get_feature_names_out()
        
        print(f"[✅] 임베딩 생성 완료")
        print(f"[📚] 어휘 크기: {vocab_size:,} 토큰")
        print(f"[🔍] 임베딩 차원: {embeddings.shape[1]:,} 차원")
        print(f"[💻] 임베딩 밀도: {embeddings.nnz / (embeddings.shape[0]*embeddings.shape[1])*100:.2f}% (희소 행렬)")
        
        # 상위 토큰 샘플 출력
        if len(feature_names) > 0:
            top_feature_sample = list(feature_names[:10])
            print(f"[🔤] 어휘 샘플: {', '.join(top_feature_sample)}{'...' if len(feature_names) > 10 else ''}")
        
        return vectorizer, embeddings
    except Exception as e:
        print(f"[❌ 오류] 임베딩 생성 중 오류 발생: {e}")
        return None, None

def find_matching_chunks(bug_report_text, code_chunks, top_n=10):
    """버그 리포트와 가장 유사한 코드 청크를 찾습니다."""
    if not code_chunks:
        print("[⚠️] 코드 청크가 없습니다. 매칭 수행 불가.")
        return []
    
    # 코드 청크 내용 목록 생성
    chunk_contents = [chunk['content'] for chunk in code_chunks]
    
    # 버그 리포트 정보
    print(f"[📄] 버그 리포트 길이: {len(bug_report_text):,} 문자")
    
    # 코드 청크 정보
    print(f"[📁] 코드 청크 수: {len(chunk_contents):,}")
    avg_chunk_size = sum(len(c) for c in chunk_contents) / len(chunk_contents) if chunk_contents else 0
    print(f"[📏] 평균 청크 크기: {avg_chunk_size:.1f} 문자")
    
    # 버그 리포트와 코드 청크를 모두 포함하는 텍스트 목록 생성
    all_texts = [bug_report_text] + chunk_contents
    
    print("\n[🧠] 임베딩 분석 시작 =========")
    # 임베딩 생성
    vectorizer, embeddings = create_embeddings(all_texts)
    
    if embeddings is None:
        print("[❌] 임베딩 생성 실패")
        return []
    
    # 버그 리포트의 임베딩은 첫 번째 항목
    bug_report_embedding = embeddings[0:1]
    
    # 코드 청크의 임베딩은 나머지 항목들
    code_chunk_embeddings = embeddings[1:]
    
    print(f"[🔄] 버그 리포트와 {len(code_chunks):,}개 코드 청크 간 유사도 계산 중...")
    # 코사인 유사도 계산
    similarities = cosine_similarity(bug_report_embedding, code_chunk_embeddings)
    
    # 기본 통계 계산 (평균, 최대, 최소 유사도)
    avg_similarity = np.mean(similarities[0])
    max_similarity = np.max(similarities[0])
    min_similarity = np.min(similarities[0])
    
    print(f"[📊] 유사도 통계: 평균={avg_similarity:.4f}, 최대={max_similarity:.4f}, 최소={min_similarity:.4f}")
    
    # 유사도가 높은 상위 N개 청크 선택
    top_indices = np.argsort(similarities[0])[-top_n:][::-1]
    
    print(f"[🏆] 상위 {top_n}개 매칭 청크 선택 완료")
    print("[🧠] 임베딩 분석 완료 =========\n")
    
    # 결과 생성
    results = []
    for i, idx in enumerate(top_indices, 1):
        chunk = code_chunks[idx]
        similarity = float(similarities[0][idx])
        file_name = os.path.basename(chunk['file_path'])
        
        results.append({
            'file_path': chunk['file_path'],
            'start_line': chunk['start_line'],
            'end_line': chunk['end_line'],
            'similarity': similarity,
            'snippet': chunk['content'][:200] + '...'  # 미리보기용 짧은 스니펫
        })
        
        # 상위 매칭 결과 로그로 출력
        print(f"[🔍 #{i}] {file_name} (유사도: {similarity:.4f})")
    
    return results

# ===== [모듈 4: 결과 요약 및 출력] =====
def format_results(matching_chunks):
    """매칭된 코드 청크를 읽기 쉬운 포맷으로 변환합니다."""
    if not matching_chunks:
        return "매칭된 코드 영역이 없습니다."
    
    result_text = "\n[🔍 버그와 관련된 상위 의심 코드 영역]\n"
    
    for i, chunk in enumerate(matching_chunks, 1):
        # 상대 경로 계산 시 다른 드라이브 간 오류 처리
        try:
            rel_path = os.path.relpath(chunk['file_path'])
        except ValueError:
            # 다른 드라이브의 경로인 경우 원래 경로 사용
            rel_path = chunk['file_path']
        
        file_name = os.path.basename(chunk['file_path'])
        
        result_text += f"\n{i}. {file_name} (유사도: {chunk['similarity']:.4f})\n"
        result_text += f"   📂 경로: {rel_path}\n"
        result_text += f"   📍 위치: {chunk['start_line']} ~ {chunk['end_line']}줄\n"
        result_text += f"   📝 코드 미리보기: \n   {chunk['snippet'].replace(chr(10), chr(10)+'   ')}\n"
    
    return result_text

def save_results(matching_chunks, output_file="bug_analysis_results.json"):
    """분석 결과를 JSON 파일로 저장합니다."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matching_chunks, f, ensure_ascii=False, indent=2)
        print(f"[✅] 분석 결과가 {output_file}에 저장되었습니다.")
    except Exception as e:
        print(f"[❌ 오류] 결과 저장 중 오류 발생: {e}")

# ===== [메인 실행 함수] =====
def main(bug_report_path=None, source_dir_path=None, output_file=None, top_n=10, chunk_size=100):
    """
    버그 리포트와 소스 코드 매칭 분석을 실행합니다.
    
    사용 방법:
    1. 함수 호출 방식 (디버깅/개발 환경): 
       main(bug_report_path="bug_report.txt", source_dir_path="C:/source_code")
       
    2. 명령줄 인자 방식 (CLI 환경):
       python Main.py --bug_report bug_report.txt --source_dir C:/source_code
    
    Args:
        bug_report_path (str, optional): 버그 리포트 파일 경로
        source_dir_path (str, optional): 소스 코드 디렉토리 경로
        output_file (str, optional): 결과 저장 파일 경로
        top_n (int, optional): 반환할 상위 매칭 개수
        chunk_size (int, optional): 코드 청크 크기 (줄 단위)
    """
    # 인자가 함수 호출로 제공되었는지 확인
    using_direct_args = bug_report_path is not None and source_dir_path is not None
    
    # 함수 호출로 인자가 제공되지 않았다면 CLI 인자 파싱
    if not using_direct_args:
        parser = argparse.ArgumentParser(description='버그 리포트와 소스 코드 자동 매칭 시스템')
        parser.add_argument('--bug_report', type=str, required=True, help='버그 리포트 파일 경로')
        parser.add_argument('--source_dir', type=str, required=True, help='소스 코드 디렉토리 경로')
        parser.add_argument('--output', type=str, default='bug_analysis_results.json', help='결과 저장 파일 경로')
        parser.add_argument('--top_n', type=int, default=10, help='반환할 상위 매칭 개수')
        parser.add_argument('--chunk_size', type=int, default=100, help='코드 청크 크기 (줄 단위)')
        
        try:
            args = parser.parse_args()
            bug_report_path = args.bug_report
            source_dir_path = args.source_dir
            output_file = args.output
            top_n = args.top_n
            chunk_size = args.chunk_size
        except SystemExit:
            print("\n[⚠️ 경고] CLI 인자 파싱 실패. 다음과 같이 사용하세요:")
            print("python Main.py --bug_report bug파일경로.txt --source_dir 소스코드경로")
            return
    
    # 기본값 설정
    if output_file is None:
        output_file = "bug_analysis_results.json"
    
    print("\n====== 버그 리포트-소스 코드 매칭 시스템 ======")
    
    # 1. 버그 리포트 로드
    print(f"\n[📄] {bug_report_path} 파일에서 버그 리포트 로드 중...")
    bug_report = load_bug_report(bug_report_path)
    
    if bug_report is None:
        return
    
    # 2. 버그 리포트 전처리 및 키워드 추출
    print("[🔍] 버그 리포트 분석 및 키워드 추출 중...")
    processed_report = preprocess_bug_report(bug_report)
    print(f"[✅] 추출된 키워드: {', '.join(processed_report['keywords'][:10])}{'...' if len(processed_report['keywords']) > 10 else ''}")
    
    # 3. 소스 파일 수집
    source_files = collect_source_files(source_dir_path)
    
    if not source_files:
        print("[❌] 소스 파일이 없습니다. 경로를 확인해주세요.")
        return
    
    # 4. 코드 청크 분할
    code_chunks = parse_code_into_chunks(source_files, chunk_size)
    
    # 5. 버그 리포트와 코드 청크 매칭
    print(f"[🔄] 버그 리포트와 코드 청크 매칭 중...")
    matching_chunks = find_matching_chunks(
        bug_report_text=bug_report,
        code_chunks=code_chunks,
        top_n=top_n
    )
    
    # 6. 결과 출력 및 저장
    print("\n" + format_results(matching_chunks))
    save_results(matching_chunks, output_file)
    
    print("\n====== 분석 완료 ======")
    
    # 결과 반환 (디버깅/개발 환경에서 활용 가능)
    return {
        "matching_chunks": matching_chunks,
        "processed_report": processed_report
    }

if __name__ == "__main__":
    # CLI 모드로 실행 (인자 없이 호출)
    main("D:/data/GersangDebugAutomation/bug_report.txt", "C:/data/Branch_Trunk_bugfix")


#flowchart TD
#    A[Bug Report 입력] --> B[LLM으로 키워드 추출]
#    B --> C[10GB 소스코드에서 관련 파일 50개 추출]
#    C --> D[각 파일에서 상단 코드 일부 추출]
#    D --> E[LLM에 버그 리포트 + 코드 전달]
#    E --> F[LLM이 분석 결과 반환: 우선 디버깅 위치]
#