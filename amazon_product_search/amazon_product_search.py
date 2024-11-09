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
    if(brand):url+="&brand="+brand;
    if(priceRange):url+="&price="+priceRange;

    # get request amazon.com
    data = requests.get(url,headers=_HEADER);

    # print the url from which these datas are extracted
    print("URL: ",url);

    # extract the datas
    soup = BeautifulSoup(data.content,"html.parser");
    searchDivs = soup.find_all("div",attrs={
        "data-component-type":"s-search-result"
    });
    datas:list = [];
    for searchDiv in searchDivs:
        data = {}
        # titles
        if(not searchDiv): continue;

        title = searchDiv.find("div",attrs={
            "data-cy":"title-recipe",
        });
        title = title.find("h2") if title else title;
        title = title.find("span").string if title else title;
        data["title"] = title;

        # links 
        link = searchDiv.find("span",attrs={
            "data-component-type":"s-product-image",
        });   
        link = "https://www.amazon.com" + link.find("a").get("href",None) if link else link;
        data["link"] = link;

        # reviews
        review = searchDiv.find("div",attrs={
        "data-cy":"reviews-block"
    });
        review = review.find("span",attrs={"class":"a-icon-alt"}) if review else review;
        review = review.string if review else review;
        data["review"] = review;

        # prices
        price = searchDiv.find("div",attrs={"data-cy":"price-recipe"});
        price = price.find("span",attrs={"class":"a-offscreen"}) if price else price;
        price = price.string if price else price
        data["price"] = price;

        # images 
        image = searchDiv.find("img",attrs={"class":"s-image"})
        image = image.get("src") if image else image
        data["image"] = image

        datas.append(data);

    return datas;

if __name__ == "__main__":
    print(amazon_product_search("iPhone",productType="electronic"));

