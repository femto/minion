import asyncio

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker

from minion.logs import logger

Base = declarative_base()


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    item_id = Column(String)  # what appears in dataset
    complexity = Column(String)
    query_range = Column(String)
    difficulty = Column(String)
    field = Column(String)
    subfield = Column(String)
    additional_attributes = Column(JSON, nullable=True)
    experiments = relationship("Experiment", back_populates="item")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    minion_name = Column(String)

    answer = Column(String)
    raw_answer = Column(String)

    correct_answer = Column(String)
    raw_correct_answer = Column(String)
    outcome = Column(String)
    score = Column(Float)
    item = relationship("Item", back_populates="experiments")


class AsyncStatsTracker:
    def __init__(self, db_url):
        # if not db_url.startswith("postgresql+asyncpg://"):
        #     raise ValueError("must starts with 'postgresql+asyncpg://' ")
        self.engine = create_async_engine(db_url, echo=True)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_db(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(e)

    async def update_stats(
        self,
        item_id,
        minion_name,
        answer,
        raw_answer,
        correct_answer,
        raw_correct_answer,
        outcome,
        complexity,
        query_range,
        difficulty,
        field,
        subfield,
        additional_attributes=None,  # Optional dictionary for extra fields
    ):
        try:
            async with self.async_session() as session:
                # Check if item exists, if not create it
                stmt = select(Item).where(Item.item_id == item_id)
                result0 = await session.execute(stmt)
                item = result0.scalar_one_or_none()

                if not item:
                    item = Item(
                        item_id=item_id,
                        complexity=complexity,
                        query_range=query_range,
                        difficulty=difficulty,
                        field=field,
                        subfield=subfield,
                        additional_attributes=additional_attributes or {},
                    )
                    session.add(item)
                else:
                    # Update existing item with new fields if needed
                    if additional_attributes:  # or assume the attributes is the same?
                        item.additional_attributes.update(additional_attributes)

                # Create new experiment
                experiment = Experiment(
                    item=item,
                    minion_name=minion_name,
                    answer=answer,
                    raw_answer=raw_answer,
                    correct_answer=correct_answer,
                    raw_correct_answer=raw_correct_answer,
                    outcome=outcome,
                )
                session.add(experiment)

                await session.commit()
        except Exception as e:
            logger.error(e)

    async def get_stats(self, item_id):
        async with self.async_session() as session:
            stmt = select(Item).options(selectinload(Item.experiments)).where(Item.item_id == item_id)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()
            if item:
                return {
                    "item_id": item.item_id,
                    "attributes": {
                        "complexity": item.complexity,
                        "query_range": item.query_range,
                        "difficulty": item.difficulty,
                        "field": item.field,
                        "subfield": item.subfield,
                    },
                    "experiments": [
                        {
                            "minion_name": exp.minion_name,
                            "answer": exp.answer,
                            "answer_raw": exp.answer_raw,
                            "correct_answer": exp.ground_truth,
                            "raw_correct_answer": exp.ground_truth_raw,
                            "outcome": exp.outcome,
                        }
                        for exp in item.experiments
                    ],
                }
            return None


async def main():
    # 使用 PostgreSQL 连接字符串
    tracker = AsyncStatsTracker("postgresql+asyncpg://用户名:密码@主机:端口/数据库名")

    # In your main function or wherever you set up your application
    await tracker.init_db()

    # In your update_stats method
    # await tracker.update_stats(
    #     item_id=self.input.item_id,
    #     minion_name=minion_name,
    #     result=result,
    #     answer_raw=answer_raw,
    #     correct_answer=self.input.correct_answer,
    #     complexity=self.input.complexity,
    #     query_range=self.input.query_range,
    #     difficulty=self.input.difficulty,
    #     field=self.input.field,
    #     subfield=self.input.subfield,
    # )
    #
    # # To retrieve stats
    # await tracker.get_stats(item_id)


if __name__ == "__main__":
    asyncio.run(main())
# Usage
