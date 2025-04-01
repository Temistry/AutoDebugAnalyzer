import os
import json
from multi_llm_analyzer import MultiLLMCodeAnalyzer

def run_example():
    """설정 파일을 사용한 다중 LLM 분석 예제"""
    
    # 설정 파일 로드
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[❌] 설정 파일 로드 실패: {e}")
        return
    
    print("[🔧] 다중 LLM 코드 분석 시스템 예제 실행")
    
    # 1. 다중 LLM 분석기 초기화
    translator_config = config['llm_servers']['translator']
    analyzer = MultiLLMCodeAnalyzer(
        translator_url=translator_config['url'],
        translator_model=translator_config['model'],
        knowledge_file=config['defaults']['knowledge_file'],
        script_dir=config['defaults']['script_dir']
    )
    
    # 2. 코드 분석 LLM 등록
    for llm_config in config['llm_servers']['code_analyzers']:
        print(f"[🔄] 코드 분석 LLM 등록: {llm_config['name']} ({llm_config['description']})")
        analyzer.add_code_llm(
            name=llm_config['name'],
            api_url=llm_config['url'],
            model_name=llm_config['model'],
            specialty=llm_config['specialty']
        )
    
    # 3. 버그 리포트 분석 예제
    example_bug_report = """
    캐릭터가 스킬을 사용할 때 가끔 게임이 멈추는 현상이 발생합니다. 
    특히 '폭풍의 일격' 스킬 사용 시 적이 죽으면서 동시에 스킬을 사용하면 크래시가 발생합니다.
    로그를 보니 CSkillUse::Action 함수에서 null 포인터 참조 오류가 발생한 것 같습니다.
    """
    
    print("\n[📄] 버그 리포트 예제:")
    print(example_bug_report)
    
    # 버그 리포트 분석
    print("\n[🔍] 버그 리포트 분석 중...")
    bug_analysis = analyzer.analyze_bug_report(example_bug_report)
    
    # 분석 결과 출력
    print("\n[📊] === 분석 결과 ===")
    print(f"버그 유형: {bug_analysis.get('bug_type', '알 수 없음')}")
    print(f"심각도: {bug_analysis.get('severity', '알 수 없음')}")
    print(f"버그 요약: {bug_analysis.get('summary', '알 수 없음')}")
    print(f"관련 키워드: {', '.join(bug_analysis.get('keywords', ['없음']))}")
    print(f"의심 함수: {', '.join(bug_analysis.get('suspected_functions', ['없음']))}")
    
    print("\n[✅] 예제 실행 완료")
    print("\n실제 사용 시에는 use_multi_llm_analyzer.py 파일을 실행하여 전체 분석 파이프라인을 사용하세요.")
    print("예시: python use_multi_llm_analyzer.py --bug_report 버그파일.txt --source_dir 소스코드경로")

if __name__ == "__main__":
    run_example() 