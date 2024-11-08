import requests
from bs4  import BeautifulSoup


def amazon_product_search(productName:str,productType:str|None=None,brand:str|None=None,priceRange:str|None=None)->dict:
    """
        Get the product lists using product type ,name ,brand and priceRange
        Parameters:
            productName:str
            productType:str (optional)
            brand:str (optional),
            priceRange:str (optional) eg. 10000-12000

        returns:
            {
                titles:list[str],
                reviews:list[str],
                prices:list[str],
                images:list[str],
                links:list[str]
            }
    """


    url:str ="https://www.amazon.com/s?" ;
    # constat header to get request amazon 
    _HEADER:dict = {
        'User-Agent':"Mozilla/5.0 (X11; Linuin zipx x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        'Accept-Language': 'en-US, en;q=0.5',
    };

    if(productName == None): raise Exception("Error prodict Name is required");
    # creating url from given data
    url+="&k="+productName;
    if(productType):url+="&i="+productType;
    if(brand):url+="&rh=p_89:="+brand;
    if(priceRange):url+="&rh=p_36:="+priceRange;

    # get request amazon.com
    data = requests.get(url,headers=_HEADER);

    # print the url from which these datas are extracted
    print("URL: ",url);

    # extract the datas
    soup = BeautifulSoup(data.content,"html.parser");

    try:
        titles = list(map( lambda x:x.find("h2").find("span").string , soup.find_all("div",attrs={
            "data-cy":"title-recipe",
        })));
        links = list(map( lambda x:"https://www.amazon.com"+x.find("a").get("href"), soup.find_all("span",attrs={
            "data-component-type":"s-product-image",
        }) ));
        reviews = list(map(lambda x:x.find("span",attrs={"class":"a-icon-alt"}).string,soup.find_all("div",attrs={
            "data-cy":"reviews-block"
        })));
        prices = list(map(lambda x:x.string,filter(lambda x:x!=None,map(lambda x:x.find("span",attrs={"class":"a-offscreen"}),soup.find_all("div",attrs={
            "data-cy":"price-recipe"
        })))));
        images = soup.find_all("img",attrs={
            "class":"s-image"
        });
    except:
        print("Invelid search query")
        return {};

    return {
        "titles":titles,
        "reviews":reviews,
        "prices":prices,
        "images":images,
        "links":links
    }

if __name__ == "__main__":
    amazon_product_search("iPhone",productType="electronic",brand="Apple",priceRange="80000-100000");

