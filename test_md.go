package main

import (
	"fmt"
	"github.com/JohannesKaufmann/html-to-markdown/v2/converter"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/base"
	"github.com/JohannesKaufmann/html-to-markdown/v2/plugin/commonmark"
)

func main() {
	html := `<strong>Bold</strong>`
	conv := converter.NewConverter(
		converter.WithPlugins(
			base.NewBasePlugin(),
			commonmark.NewCommonmarkPlugin(),
		),
	)
	md, err := conv.ConvertString(html)
	if err != nil {
		fmt.Println("Error:", err)
		return
	}
	fmt.Println(md)
}

