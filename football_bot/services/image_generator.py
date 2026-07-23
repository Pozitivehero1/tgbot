# ... импорты
import aiofiles
import aiohttp

# В классе ImageGenerator добавляем:

    def __init__(self, image_search_service = None) -> None:
        settings = get_settings()
        self._output_dir = Path(settings.images_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._width = settings.card_width
        self._height = settings.card_height
        self._image_search = image_search_service  # опционально

    async def _download_image(self, url: str, dest_path: Path) -> Optional[str]:
        """Скачивает изображение по URL и сохраняет в dest_path."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(dest_path, 'wb') as f:
                            f.write(await response.read())
                        logger.info("image_downloaded", path=str(dest_path))
                        return str(dest_path)
                    else:
                        logger.warning("image_download_failed", status=response.status, url=url)
                        return None
        except Exception as exc:
            logger.warning("image_download_error", error=str(exc), url=url)
            return None

    async def get_photo_for_publication(self, pub: Publication, source_item: Optional[NewsItem] = None, match: Optional[Match] = None) -> Optional[str]:
        """Попытаться найти реальное фото для публикации. Если найдено — скачать и вернуть путь."""
        if not self._image_search:
            return None

        # Генерируем поисковый запрос в зависимости от формата
        query = None
        if pub.format == PublicationFormat.BREAKING_NEWS or pub.format == PublicationFormat.TRANSFER_NEWS:
            # Если есть source_item — используем его заголовок для поиска
            if source_item:
                # Убираем лишнее из заголовка для поиска
                title_words = source_item.title.split()
                # Берём первые 5 слов
                query = " ".join(title_words[:5])
            else:
                query = pub.title
        elif pub.format == PublicationFormat.INTERESTING_FACT:
            # Для фактов ищем по теме (берём первые 4 слова)
            query = " ".join(pub.title.split()[:4])
        elif match:
            query = f"{match.home_team} vs {match.away_team} football"
        else:
            query = "football"

        if not query:
            return None

        photo_url = await self._image_search.search_photo(query)
        if not photo_url:
            return None

        # Скачиваем фото в папку images
        dest_path = self._output_dir / f"real_{uuid.uuid4().hex[:8]}.jpg"
        local_path = await self._download_image(photo_url, dest_path)
        return local_path
