from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from starlette.concurrency import run_in_threadpool
from .poker import equity
from .advisor_api import ImageRequest

router=APIRouter(prefix='/api/poker')


class PokerImageRequest(ImageRequest):
    hole_roi:list[float]=Field(min_length=4,max_length=4)
    board_roi:list[float]=Field(min_length=4,max_length=4)


@router.post('/image')
async def inspect_image(body:PokerImageRequest):
    import base64,io
    from PIL import Image
    from .poker_vision import inspect
    def read():
        raw=base64.b64decode(body.image_base64,validate=True)
        if len(raw)>8*1024*1024:raise ValueError('Image exceeds 8 MiB.')
        with Image.open(io.BytesIO(raw)) as source:
            if source.width*source.height>5_000_000:raise ValueError('Image exceeds five megapixels.')
            return inspect(source.convert('RGB'),body.hole_roi,body.board_roi)
    try:return await run_in_threadpool(read)
    except (ValueError,TypeError,OSError,Image.DecompressionBombError) as error:
        raise HTTPException(422,str(error)) from error


class EquityRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    hole:list[str]=Field(min_length=2,max_length=2)
    board:list[str]=Field(default_factory=list,max_length=5)
    dead:list[str]=Field(default_factory=list,max_length=45)
    opponents:int=Field(default=1,ge=1,le=8)
    samples:int=Field(default=2000,ge=100,le=20000)
    seed:int=42
    opponent_ranges:list[list[list[str]]|None]|None=None
    pot:float=Field(default=0,ge=0,allow_inf_nan=False)
    call_cost:float=Field(default=0,ge=0,allow_inf_nan=False)


@router.post('/equity')
async def calculate(body:EquityRequest):
    try:
        return await run_in_threadpool(equity,body.hole,body.board,opponents=body.opponents,
            samples=body.samples,seed=body.seed,dead=body.dead,opponent_ranges=body.opponent_ranges,
            pot=body.pot,call_cost=body.call_cost)
    except (ValueError,TypeError) as error:
        raise HTTPException(422,str(error)) from error
