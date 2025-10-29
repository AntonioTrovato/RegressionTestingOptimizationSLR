library(ggplot2)

theme_luigi <- function() {
  theme_gray() +
  theme( #custom parts
    #axis.text.x = element_text(angle = 45, hjust = 1),
    #legend.position = "bottom",
    #plot.title = element_text(face = "bold", size = 14),
    #panel.grid.major = element_line(color = "grey80"),
    #panel.grid.minor = element_blank()
  )
}
