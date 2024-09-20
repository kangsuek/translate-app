import requests
from bs4 import BeautifulSoup
import html2text
import markdown
from weasyprint import HTML
import sys

def extract_main_content(soup):
    # 주요 콘텐츠를 포함할 가능성이 높은 태그들
    content_tags = ['article', 'main', 'div[id*="content"]', 'div[class*="content"]']
    
    for tag in content_tags:
        content = soup.select_one(tag)
        if content:
            return content
    
    # 주요 콘텐츠를 찾지 못한 경우 body 전체를 반환
    return soup.body

def web_to_markdown(url):
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 주요 콘텐츠 추출
        main_content = extract_main_content(soup)
        
        # HTML을 마크다운으로 변환
        h = html2text.HTML2Text()
        h.ignore_links = False
        markdown_content = h.handle(str(main_content))
        
        return markdown_content
    except requests.RequestException as e:
        print(f"웹 페이지를 가져오는 중 오류 발생: {e}")
        sys.exit(1)

def markdown_to_pdf(markdown_content, output_file):
    try:
        html_content = markdown.markdown(markdown_content)
        
        css = """
        <style>
            body { font-family: Arial, sans-serif; margin: 0 auto; max-width: 800px; padding: 20px; }
            h1, h2, h3 { color: #333366; }
            p { line-height: 1.6; }
            img { max-width: 100%; height: auto; }
        </style>
        """
        html_content = f"<html><head>{css}</head><body>{html_content}</body></html>"
        
        HTML(string=html_content).write_pdf(output_file)
    except Exception as e:
        print(f"PDF 생성 중 오류 발생: {e}")
        sys.exit(1)

def web_to_pdf(url, output_file):
    markdown_content = web_to_markdown(url)
    
    # 마크다운 파일 생성
    markdown_file = output_file.rsplit('.', 1)[0] + '.md'
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"마크다운 파일이 생성되었습니다: {markdown_file}")
    
    markdown_to_pdf(markdown_content, output_file)
    print(f"PDF 파일이 생성되었습니다: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python webToPdf.py <URL> <출력_파일명>")
        sys.exit(1)
    
    url = sys.argv[1]
    output_file = sys.argv[2]
    
    web_to_pdf(url, output_file)
